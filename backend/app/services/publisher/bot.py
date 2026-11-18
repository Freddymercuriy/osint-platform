"""Telegram Bot API mijozi — `httpx` ustida, bot framework'siz (rahbariyat kanali uchun ~11 ta usul).

Xavfsizlik (token = kanalga post qilish huquqi):
- Token faqat `TG_BOT_TOKEN` (backend/.env) da. So'rov URL'ida bo'ladi (`/bot<token>/<method>`), shuning uchun:
  - `raise_for_status()` chaqirilmaydi — httpx xato matniga URL'ni (token bilan) qo'yadi; javob JSON'idan
    `ok`, `error_code`, `description`, `parameters` o'qiladi;
  - har xato matni `redact()` dan o'tadi, httpx istisnosi zanjirga qo'shilmaydi (`from None`) — traceback'da ham
    token chiqmaydi;
  - `httpx` loggeriga (INFO: "HTTP Request: POST https://api.telegram.org/bot<token>/...") token yashiruvchi filtr.
- Xatolar turlarga ajratiladi — chaqiruvchi ular bo'yicha qaror qiladi (kutish, to'xtatish, ogohlantirish).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

log = logging.getLogger("osint.publisher")

API_BASE = "https://api.telegram.org"
# Bot tokeni ko'rinishi: <bot id>:<35 belgili maxfiy qism>. Noma'lum (boshqa) token ham yashirilsin.
TOKEN_RE = re.compile(r"\d{5,16}:[A-Za-z0-9_-]{30,}")
REDACTED = "<token>"

# Testlar almashtiradi (httpx.MockTransport)
TRANSPORT: httpx.AsyncBaseTransport | None = None


def redact(text: Any, token: str | None = None) -> str:
    """Matndagi bot tokenini (sozlamadagisi va istalgan token ko'rinishidagi satr) `<token>` bilan almashtiradi."""
    if text is None:
        return ""
    s = str(text)
    for tok in (token, settings.tg_bot_token):
        if tok:
            s = s.replace(tok, REDACTED)
    return TOKEN_RE.sub(REDACTED, s)


class _RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001 — formatlash xatosi logni to'xtatmasin
            return True
        clean = redact(msg)
        if clean != msg:
            record.msg, record.args = clean, None
        return True


_FILTER = _RedactFilter()
for _name in ("httpx", "httpcore", "osint.publisher"):
    _lg = logging.getLogger(_name)
    if _FILTER not in _lg.filters:
        _lg.addFilter(_FILTER)


# ---------------------------------------------------------------- xato turlari
class BotError(Exception):
    """Bot API xatosi. `kind` — chaqiruvchi qaror qiladigan tur; matnda token yo'q."""

    kind = "error"

    def __init__(self, description: str, *, method: str = "", code: int | None = None,
                 retry_after: float | None = None, migrate_to_chat_id: int | None = None) -> None:
        self.description = redact(description)[:500]
        self.method = method
        self.code = code
        self.retry_after = retry_after
        self.migrate_to_chat_id = migrate_to_chat_id
        prefix = f"{method}: " if method else ""
        code_txt = f"{code} " if code else ""
        super().__init__(f"{prefix}{code_txt}{self.description}".strip())


class BotTokenMissing(BotError):
    kind = "token_missing"


class BotRateLimited(BotError):
    """429 — `retry_after` soniya kutish kerak."""

    kind = "rate_limited"


class BotUnauthorized(BotError):
    """401 / 404 — token noto'g'ri yoki bekor qilingan: hamma joyga yuborish to'xtaydi."""

    kind = "unauthorized"


class BotForbidden(BotError):
    """403 — bot kanaldan chiqarilgan yoki huquqi yo'q: shu manzilga yuborish to'xtaydi."""

    kind = "forbidden"


class BotBadRequest(BotError):
    """400 — so'rov xato (formatlash, juda uzun, chat topilmadi ...)."""

    kind = "bad_request"

    @property
    def _d(self) -> str:
        return self.description.lower()

    @property
    def is_parse_error(self) -> bool:
        return "can't parse entities" in self._d or "can't find end" in self._d or "unsupported start tag" in self._d

    @property
    def chat_not_found(self) -> bool:
        return "chat not found" in self._d or "chat_id is empty" in self._d or "peer_id_invalid" in self._d

    @property
    def photo_rejected(self) -> bool:
        """Telegram rasm faylini qabul qilmadi (o'lcham, format, ishlov xatosi)."""
        d = self._d
        return any(k in d for k in ("photo_invalid", "image_process_failed", "photo_ext_invalid", "photo_save_file",
                                    "wrong file", "file is too big", "photo_crop", "failed to get http url content",
                                    "wrong type of the web page content", "photo_invalid_dimensions"))

    @property
    def too_long(self) -> bool:
        return "too long" in self._d

    @property
    def not_modified(self) -> bool:
        return "message is not modified" in self._d

    @property
    def message_gone(self) -> bool:
        return ("message to edit not found" in self._d or "message to delete not found" in self._d
                or "message can't be edited" in self._d or "message can't be deleted" in self._d)


class BotConflict(BotError):
    """409 — webhook o'rnatilgan yoki boshqa jarayon ham getUpdates qilyapti."""

    kind = "conflict"


class BotNetworkError(BotError):
    """Tarmoq / vaqt tugashi / Telegram 5xx — eksponensial kutish bilan qayta urinish."""

    kind = "network"


def error_from(method: str, code: int | None, description: str, parameters: dict | None) -> BotError:
    params = parameters or {}
    kw: dict[str, Any] = {"method": method, "code": code}
    if params.get("migrate_to_chat_id") is not None:
        kw["migrate_to_chat_id"] = params.get("migrate_to_chat_id")
    if code == 429:
        try:
            retry = float(params.get("retry_after") or 0) or None
        except (TypeError, ValueError):
            retry = None
        return BotRateLimited(description or "Too Many Requests", retry_after=retry or 5.0, **kw)
    if code in (401, 404):  # noto'g'ri token — Telegram 401 Unauthorized yoki 404 Not Found qaytaradi
        return BotUnauthorized(description or "Unauthorized", **kw)
    if code == 403:
        return BotForbidden(description or "Forbidden", **kw)
    if code == 409:
        return BotConflict(description or "Conflict", **kw)
    if code == 400:
        return BotBadRequest(description or "Bad Request", **kw)
    if code is not None and code >= 500:
        return BotNetworkError(description or f"HTTP {code}", **kw)
    return BotError(description or "Unknown error", **kw)


# ---------------------------------------------------------------- mijoz
@dataclass
class SentMessage:
    message_id: int
    chat_id: int | None
    date: int | None
    text: str | None
    entities: list[dict]
    raw: dict


def sent_of(result: dict) -> SentMessage:
    return SentMessage(
        message_id=int(result.get("message_id") or 0),
        chat_id=(result.get("chat") or {}).get("id"),
        date=result.get("date"),
        text=result.get("text") if result.get("text") is not None else result.get("caption"),
        entities=list(result.get("entities") or result.get("caption_entities") or []),
        raw=result,
    )


def _form_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, dict | list):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


class BotClient:
    """Bot API'ga asinxron mijoz. Bitta `httpx.AsyncClient` (ulanishlar qayta ishlatiladi)."""

    def __init__(self, token: str, *, transport: httpx.AsyncBaseTransport | None = None,
                 timeout: float = 30.0, base_url: str = API_BASE) -> None:
        if not token:
            raise BotTokenMissing("TG_BOT_TOKEN berilmagan")
        self._token = token
        self._base = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            transport=transport if transport is not None else TRANSPORT,
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={"User-Agent": "osint-platform-publisher/1.0"},
            follow_redirects=False,
        )

    def __repr__(self) -> str:  # tokenni hech qayerda ko'rsatmaslik
        return "BotClient(<token>)"

    async def aclose(self) -> None:
        await self._http.aclose()

    async def call(self, method: str, params: dict[str, Any] | None = None, *,
                   files: dict[str, tuple[str, bytes, str]] | None = None, timeout: float | None = None) -> Any:
        url = f"{self._base}/bot{self._token}/{method}"
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            if files:
                resp = await self._http.post(url, data={k: _form_value(v) for k, v in clean.items()}, files=files,
                                             timeout=timeout)
            else:
                resp = await self._http.post(url, json=clean, timeout=timeout)
        except httpx.TimeoutException:
            raise BotNetworkError("vaqt tugadi (timeout)", method=method) from None
        except httpx.HTTPError as exc:
            raise BotNetworkError(f"{type(exc).__name__}: {redact(exc, self._token)}", method=method) from None
        try:
            body = resp.json()
        except ValueError:
            raise error_from(method, resp.status_code if resp.status_code >= 400 else 502,
                             f"javob JSON emas (HTTP {resp.status_code})", None) from None
        if not isinstance(body, dict):
            raise BotNetworkError("kutilmagan javob", method=method, code=resp.status_code)
        if body.get("ok"):
            return body.get("result")
        raise error_from(method, body.get("error_code") or resp.status_code,
                         redact(body.get("description") or "", self._token), body.get("parameters"))

    # -------------------------------------------------------- usullar
    async def get_me(self) -> dict:
        return await self.call("getMe")

    async def get_webhook_info(self) -> dict:
        return await self.call("getWebhookInfo")

    async def get_updates(self, offset: int | None, *, timeout: int = 25, limit: int = 100,
                          allowed_updates: list[str] | None = None) -> list[dict]:
        return await self.call("getUpdates", {
            "offset": offset, "timeout": timeout, "limit": limit, "allowed_updates": allowed_updates,
        }, timeout=timeout + 15) or []

    async def get_chat(self, chat_id: int | str) -> dict:
        return await self.call("getChat", {"chat_id": chat_id})

    async def get_chat_member(self, chat_id: int | str, user_id: int) -> dict:
        return await self.call("getChatMember", {"chat_id": chat_id, "user_id": user_id})

    async def send_message(self, chat_id: int | str, text: str, *, parse_mode: str | None = "HTML",
                           silent: bool = False, protect_content: bool = False, reply_to: int | None = None,
                           reply_markup: dict | None = None, thread_id: int | None = None) -> SentMessage:
        params: dict[str, Any] = {
            "chat_id": chat_id, "text": text, "parse_mode": parse_mode,
            "link_preview_options": {"is_disabled": True},
            "disable_notification": silent or None, "protect_content": protect_content or None,
            "reply_markup": reply_markup, "message_thread_id": thread_id,
        }
        if reply_to:
            params["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        return sent_of(await self.call("sendMessage", params))

    async def send_photo(self, chat_id: int | str, photo: bytes, *, caption: str | None = None,
                         parse_mode: str | None = "HTML", silent: bool = False, protect_content: bool = False,
                         reply_markup: dict | None = None, thread_id: int | None = None, reply_to: int | None = None,
                         filename: str = "chart.png", content_type: str = "image/png") -> SentMessage:
        params: dict[str, Any] = {
            "chat_id": chat_id, "caption": caption, "parse_mode": parse_mode if caption else None,
            "disable_notification": silent or None, "protect_content": protect_content or None,
            "reply_markup": reply_markup, "message_thread_id": thread_id,
        }
        if reply_to:
            params["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        return sent_of(await self.call("sendPhoto", params, files={"photo": (filename, photo, content_type)},
                                       timeout=60.0))

    async def edit_message_text(self, chat_id: int | str, message_id: int, text: str, *,
                                parse_mode: str | None = "HTML", reply_markup: dict | None = None) -> Any:
        return await self.call("editMessageText", {
            "chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode,
            "link_preview_options": {"is_disabled": True}, "reply_markup": reply_markup,
        })

    async def edit_message_reply_markup(self, chat_id: int | str, message_id: int,
                                        reply_markup: dict | None = None) -> Any:
        return await self.call("editMessageReplyMarkup", {
            "chat_id": chat_id, "message_id": message_id,
            "reply_markup": reply_markup if reply_markup is not None else {"inline_keyboard": []},
        })

    async def delete_message(self, chat_id: int | str, message_id: int) -> bool:
        return bool(await self.call("deleteMessage", {"chat_id": chat_id, "message_id": message_id}))

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None, *,
                                    show_alert: bool = False) -> bool:
        return bool(await self.call("answerCallbackQuery", {
            "callback_query_id": callback_query_id, "text": (text or None) and text[:200],
            "show_alert": show_alert or None,
        }))


def token_configured() -> bool:
    return bool((settings.tg_bot_token or "").strip())


def make_client(*, transport: httpx.AsyncBaseTransport | None = None) -> BotClient:
    """Sozlamadagi token bilan mijoz; token yo'q bo'lsa `BotTokenMissing`."""
    token = (settings.tg_bot_token or "").strip()
    if not token:
        raise BotTokenMissing("TG_BOT_TOKEN berilmagan")
    return BotClient(token, transport=transport)
