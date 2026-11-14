"""Telegram — foydalanuvchining o'z akkaunti orqali (Telethon, MTProto).

config: {} — `TG_CHATS` dagi barcha chatlar (v1 xatti-harakati), yoki {"chat": "username yoki -100id"} — bitta chat.
Filtr: `TG_UZ_FILTER=true` bo'lsa Markaziy Osiyo kalit so'zlari, qo'shimcha `TG_EXTRA_KEYWORDS`.
Guruhlardagi yuboruvchi ismi/telefoni o'qilmaydi va saqlanmaydi — faqat xabar matni parchasi va havola.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.services.connectors.base import (
    AuthMissing,
    Connector,
    ConnectorError,
    FetchContext,
    FetchResult,
    RateLimited,
    RawItem,
    register,
)
from app.services.events.filters import _kw_regex, _match_snippet, _UZ_PATTERNS


def keyword_patterns():
    from app.core.config import settings

    extra = [(k, _kw_regex(k, whole_word=True)) for k in settings.tg_extra_keywords_list]
    return (_UZ_PATTERNS + extra) if settings.tg_uz_filter else extra


def messages_to_items(messages, leak_keys: list[str], patterns) -> list[RawItem]:
    from app.services import telegram_user as tg

    items: list[RawItem] = []
    seen: set[str] = set()
    # Yangilari birinchi — takrorlarda eng yangisi qoladi
    for m in sorted(messages, key=lambda x: x.date or datetime.min.replace(tzinfo=UTC), reverse=True):
        hits, snippet = _match_snippet(m.text, patterns)
        if patterns and not hits:
            continue
        fingerprint = re.sub(r"\W+", "", m.text.lower())[:200]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        first = m.text.strip().split("\n")[0]
        is_leak = bool(leak_keys) and tg.chat_matches(m.chat, leak_keys)
        items.append(RawItem(
            title=first[:140] + ("..." if len(first) > 140 else ""),
            url=m.url, summary=snippet, published=m.date,
            source_name=f"TG: {m.chat.title}"[:128],
            category="leak" if is_leak else None,
            channel="telegram_group" if m.chat.kind == "group" else "telegram_channel",
            matched_keywords=hits,
            extra={"chat_id": m.chat.id},
        ))
    return items


@register
class TelegramUserConnector(Connector):
    kind = "telegram_user"
    title = "Telegram (o'z akkauntingiz orqali)"
    config_fields = ("chat",)
    uses_http = False

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        from telethon import errors

        from app.core.config import settings
        from app.services import telegram_user as tg

        if not tg.is_configured():
            raise AuthMissing("TG_API_ID / TG_API_HASH sozlanmagan")
        chat = (ctx.source.config.get("chat") or "").strip()
        try:
            if chat:
                messages = await tg.fetch_chat_messages(chat, settings.tg_messages_per_chat)
            else:
                messages = await tg.fetch_messages()
        except tg.TelegramNotConfigured as exc:
            raise AuthMissing(str(exc)) from exc
        except errors.FloodWaitError as exc:
            raise RateLimited(f"Telegram FloodWait {exc.seconds} s", retry_after=float(exc.seconds)) from exc
        except (ValueError, errors.RPCError) as exc:
            raise ConnectorError(f"Telegram: {type(exc).__name__}: {exc}") from exc
        items = messages_to_items(messages, settings.tg_leak_chats_list, keyword_patterns())
        return FetchResult(items, None)
