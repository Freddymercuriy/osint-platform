"""Tarjima provayderi: o'z NLLB servisimiz (facebook/nllb-200), kalitsiz — `TRANSLATE_API_URL`.

Servis FLORES-200 / NLLB til kodlarini kutadi (`uzn_Latn`, `rus_Cyrl`, `eng_Latn` ...), platforma esa ISO kodlarini
ishlatadi (`uz`, `ru`, `en` ...) — `NLLB_CODES` jadvali (NLLB kodlarining o'zi ham qabul qilinadi). Manba tili har doim
aniq beriladi: uni navbatga qo'yishdan oldin `text.detect_lang` aniqlaydi (servisda avto-aniqlash yo'q).

O'zbek kirill (`uz-Cyrl` / `uzn_Cyrl`): servisda `uzn_Cyrl` yo'q, shuning uchun model `uzn_Latn` bilan ishlaydi, yozuv esa
latin.jaybi.uz dvigateli (`vendor/uztranslit.py`) bilan almashtiriladi — manba kirill bo'lsa avval lotinga, maqsad
`uzn_Cyrl` bo'lsa tarjima lotinda olinib kirillga o'giriladi. O'zbek ↔ o'zbek (lotin ↔ kirill) — servissiz, faqat yozuv.

- `NllbTranslator.translate` — navbat (worker) uchun: xatoda **istisno** ko'taradi, worker qatorni `pending` da
  qoldirib keyinroq qayta urinadi (asl matn tarjima sifatida keshga yozilib qolmasin).
- `translate_or_original` — navbatdan tashqaridagi to'g'ridan-to'g'ri chaqiruvlar uchun: xatoda ogohlantirish yozib
  asl matnni qaytaradi.

Paketlar: `/translate/batch` ga ≤ 64 matn; `max_input_length` (`GET /model`, token) dan uzun matnlar gaplar bo'yicha
bo'linadi (belgilar soni ≤ tokenlar — xavfsiz chegara) va tarjimadan keyin qayta birlashtiriladi. `/model` javob
bermasa — standart chegara olinadi va 10 daqiqa so'ralmaydi (sekin servisda har paket oldidan kutib qolmaslik uchun).
Qayta urinish: ulanish xatosi va 5xx — 2 marta (1 s, 2 s + jitter); timeout (`TranslationTimeout` — worker paketni
bo'lib qayta yuboradi) va 422 — qayta urinilmaydi.
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import re
import time
from typing import Protocol

import httpx

from app.services.connectors.base import ConfigError, ConnectorError, RateLimited
from app.services.connectors.http import HttpFetcher, parse_retry_after
from app.services.i18n.text import is_cyrillic, uz_to_cyrillic, uz_to_latin

log = logging.getLogger("osint.i18n")

MAX_STRINGS = 64  # /translate/batch: texts maxItems = 64 (servis sxemasi)
MAX_CHARS = 12_000  # worker paketidagi belgilar — bitta so'rovning GPU vaqtini (va timeout xavfini) cheklaydi
DEFAULT_MAX_INPUT = 512  # `GET /model` javob bermasa
TOKEN_RESERVE = 8  # til belgisi va </s> uchun zaxira
RETRIES = 2
RETRY_BASE = 1.0  # soniya; testlar 0 qiladi

# Platforma kodi → FLORES-200 / NLLB (har biri `GET /languages` bilan tekshirilgan, 2026-11-16)
NLLB_CODES = {
    "uz": "uzn_Latn",
    "ru": "rus_Cyrl",
    "en": "eng_Latn",
    "kk": "kaz_Cyrl",
    "ky": "kir_Cyrl",
    "tg": "tgk_Cyrl",
    "tk": "tuk_Latn",
}
_BY_NLLB = {v.lower(): v for v in NLLB_CODES.values()}  # "rus_cyrl" → "rus_Cyrl"
UZN = "uzn_Latn"
# Servisda yo'q — uzn_Latn + latin.jaybi.uz lotin → kirill
UZ_CYRILLIC = frozenset({"uz-cyrl", "uz_cyrl", "uzn_cyrl"})

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
# base_url → (max_input_length, amal qilish muddati — time.monotonic; servis javobi — cheksiz, standart qiymat — vaqtincha)
_max_input_cache: dict[str, tuple[int, float]] = {}
MODEL_RETRY_SECONDS = 600.0


class UnsupportedLanguage(ConnectorError):
    """Platforma kodi uchun NLLB kodi yo'q — so'rov yuborilmaydi."""


class TranslationRequestError(ConnectorError):
    """Servis so'rovni rad etdi (HTTP 422) — qayta urinish foyda bermaydi."""


class TranslationTimeout(ConnectorError):
    """Servis belgilangan vaqtda javob bermadi — paket katta bo'lishi mumkin (worker uni bo'lib qayta yuboradi)."""


class Translator(Protocol):
    name: str

    @property
    def configured(self) -> bool: ...

    async def translate(self, texts: list[str], source: str, target: str) -> list[str]: ...


def to_nllb(code: str) -> str:
    """Platforma (`uz`, `uz-Cyrl` ...) yoki NLLB kodi → servis kodi. O'zbek kirill → `uzn_Latn` (yozuv alohida)."""
    key = (code or "").lower()
    if key in UZ_CYRILLIC:
        return UZN
    if key in NLLB_CODES:
        return NLLB_CODES[key]
    if key in _BY_NLLB:
        return _BY_NLLB[key]
    raise UnsupportedLanguage(f"Tarjima servisi uchun til kodi yo'q: {code!r}")


def split_text(text: str, limit: int) -> list[str]:
    """`limit` belgidan uzun matn — gaplar bo'yicha bo'laklar (har biri ≤ limit); juda uzun gap — bo'sh joydan."""
    text = text.strip()
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    cur = ""
    for sentence in _SENTENCE_END.split(text):
        for piece in _hard_split(sentence.strip(), limit):
            if cur and len(cur) + 1 + len(piece) > limit:
                chunks.append(cur)
                cur = piece
            else:
                cur = f"{cur} {piece}" if cur else piece
    if cur:
        chunks.append(cur)
    return chunks


def _hard_split(sentence: str, limit: int):
    while len(sentence) > limit:
        cut = sentence.rfind(" ", 0, limit + 1)
        if cut <= 0:
            cut = limit
        yield sentence[:cut].strip()
        sentence = sentence[cut:].strip()
    if sentence:
        yield sentence


def _detail(resp: httpx.Response) -> str:
    """422 javobidagi `detail: [{loc, msg}]` → "texts.0: ...; source_lang: ..."."""
    try:
        detail = resp.json().get("detail")
    except ValueError:
        return resp.text[:300]
    if isinstance(detail, list):
        parts = []
        for d in detail[:5]:
            loc = ".".join(str(x) for x in (d.get("loc") or []) if x != "body")
            parts.append(f"{loc}: {d.get('msg')}" if loc else str(d.get("msg")))
        return "; ".join(parts)
    return str(detail)[:300]


class NllbTranslator:
    name = "nllb"

    def __init__(self, base_url: str | None, http: HttpFetcher, timeout: float = 30.0) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.http = http
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    async def translate(self, texts: list[str], source: str, target: str) -> list[str]:
        if not texts:
            return []
        src, tgt = to_nllb(source), to_nllb(target)
        to_cyr = (target or "").lower() in UZ_CYRILLIC
        if src == tgt:
            if src == UZN:  # o'zbek lotin ↔ kirill — model kerak emas
                return [uz_to_cyrillic(t) if to_cyr else uz_to_latin(t) for t in texts]
            return list(texts)
        if not self.base_url:
            raise ConnectorError("TRANSLATE_API_URL sozlanmagan")
        limit = await self.chunk_chars()
        pieces: list[str] = []
        spans: list[tuple[int, int]] = []
        for text in texts:
            if src == UZN and is_cyrillic(text):
                text = uz_to_latin(text)  # servisda uzn_Cyrl yo'q — latin.jaybi.uz qoidalari bilan lotinga
            parts = split_text(text, limit) if text.strip() else []
            spans.append((len(pieces), len(parts)))
            pieces.extend(parts)
        out: list[str] = []
        for i in range(0, len(pieces), MAX_STRINGS):
            out.extend(await self._batch(pieces[i:i + MAX_STRINGS], src, tgt))
        result = [" ".join(out[start:start + n]) for start, n in spans]
        return [uz_to_cyrillic(r) for r in result] if to_cyr else result

    async def chunk_chars(self) -> int:
        """Bitta bo'lakning belgilar chegarasi: `max_input_length` (token) − zaxira.

        Servis javobi jarayon davomida keshlanadi; javob bo'lmasa standart qiymat `MODEL_RETRY_SECONDS` ga keshlanadi.
        """
        hit = _max_input_cache.get(self.base_url)
        if hit is None or hit[1] <= time.monotonic():
            try:
                data = await self._request("GET", "/model")
                hit = (int(data.get("max_input_length") or DEFAULT_MAX_INPUT), math.inf)
            except (ConnectorError, ValueError, TypeError) as exc:
                log.warning("Tarjima servisi /model javob bermadi (%s) — %d token deb olinadi, %d daqiqadan keyin "
                            "qayta so'raladi", exc, DEFAULT_MAX_INPUT, MODEL_RETRY_SECONDS // 60)
                hit = (DEFAULT_MAX_INPUT, time.monotonic() + MODEL_RETRY_SECONDS)
            _max_input_cache[self.base_url] = hit
        return max(64, hit[0] - TOKEN_RESERVE)

    async def _batch(self, texts: list[str], src: str, tgt: str) -> list[str]:
        data = await self._request("POST", "/translate/batch",
                                   json={"texts": texts, "source_lang": src, "target_lang": tgt})
        results = data.get("results") or []
        if len(results) != len(texts):
            raise ConnectorError(f"Tarjima servisi: {len(texts)} ta matn uchun {len(results)} ta javob")
        return [r.get("translation") or "" for r in results]

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        url = self.base_url + path
        timeout = httpx.Timeout(self.timeout, connect=min(10.0, self.timeout))
        for attempt in range(RETRIES + 1):
            last = attempt == RETRIES
            try:
                resp = await self.http.request(method, url, raise_errors=False, timeout=timeout, **kwargs)
            except ConfigError:
                raise  # taqiqlangan manzil va h.k. — takrorlash ma'nosiz
            except ConnectorError as exc:
                if isinstance(exc.__cause__, httpx.TimeoutException):
                    # og'ir GPU so'rovini darhol takrorlash yukni oshiradi — navbat keyinroq qayta uradi
                    raise TranslationTimeout(f"Tarjima servisi {self.timeout:g} s ichida javob bermadi ({path})") from exc
                if last:
                    raise ConnectorError(f"Tarjima servisiga ulanib bo'lmadi ({path}): {exc}") from exc
                await self._backoff(attempt, f"ulanish xatosi: {exc}")
                continue
            code = resp.status_code
            if code == 200:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise ConnectorError(f"Tarjima servisi: JSON emas javob ({path})") from exc
            if code == 422:
                raise TranslationRequestError(f"Tarjima servisi so'rovni rad etdi (422): {_detail(resp)}",
                                              http_status=422)
            if code == 429:
                raise RateLimited("Tarjima servisi: juda ko'p so'rov (429)", http_status=429,
                                  retry_after=parse_retry_after(resp.headers.get("retry-after")) or 60)
            if code >= 500 and not last:
                await self._backoff(attempt, f"HTTP {code}")
                continue
            raise ConnectorError(f"Tarjima servisi: HTTP {code} ({path})", http_status=code)
        raise AssertionError("unreachable")

    @staticmethod
    async def _backoff(attempt: int, reason: str) -> None:
        delay = RETRY_BASE * 2 ** attempt + random.uniform(0, RETRY_BASE / 2)
        log.info("Tarjima servisi: %s — %.1f s dan keyin qayta urinish", reason, delay)
        await asyncio.sleep(delay)


async def translate_or_original(translator: Translator, texts: list[str], source: str, target: str) -> list[str]:
    """Navbatdan tashqaridagi chaqiruvlar uchun: tarjima bo'lmasa — ogohlantirish va asl matn (hech qachon xato emas).

    Navbat (worker) buni ishlatmaydi: u yerda asl matn tarjima sifatida saqlanib qolmasligi uchun xato kerak.
    """
    try:
        return await translator.translate(texts, source, target)
    except Exception as exc:  # noqa: BLE001 — fallback'ning o'zi shu
        log.warning("Tarjima bajarilmadi (%s→%s, %d ta matn) — asl matn qaytarildi: %s",
                    source, target, len(texts), exc)
        return list(texts)


class FakeTranslator:
    """Testlar uchun: "[target] matn" qaytaradi va chaqiruvlarni yozib boradi."""

    name = "fake"

    def __init__(self, fail: Exception | None = None, cyrillic_uz: bool = False) -> None:
        self.calls: list[tuple[str, str, list[str]]] = []
        self.fail = fail
        self.cyrillic_uz = cyrillic_uz

    @property
    def configured(self) -> bool:
        return True

    async def translate(self, texts: list[str], source: str, target: str) -> list[str]:
        self.calls.append((source, target, list(texts)))
        if self.fail:
            raise self.fail
        if target == "uz" and self.cyrillic_uz:
            return [f"Ўзбекча: {t}" for t in texts]
        return [f"[{target}] {t}" for t in texts]
