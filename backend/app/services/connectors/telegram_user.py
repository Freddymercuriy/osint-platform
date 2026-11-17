"""Telegram — foydalanuvchining o'z akkaunti orqali (Telethon, MTProto).

config: {} — `TG_CHATS` dagi barcha chatlar (v1 xatti-harakati), yoki {"chat": "username yoki -100id"} — bitta chat.
Filtr: `TG_UZ_FILTER=true` bo'lsa Markaziy Osiyo kalit so'zlari, qo'shimcha `TG_EXTRA_KEYWORDS`.
Manba `scope = global` bo'lsa kalit so'z talab qilinmaydi (mavzu — manbaning `cyber_filter` bayrog'ida), kalit so'z
topilgan xabar esa `regional` (asosiy lenta) bo'ladi.
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


def messages_to_items(messages, leak_keys: list[str], patterns, *, global_scope: bool = False) -> list[RawItem]:
    """`global_scope` — kalit so'z topilmagan xabar ham qoladi (mavzu filtri manba bayroqlarida), topilgani esa
    `regional` deb belgilanadi (asosiy lentaga; `apply_filters` uni kiber mavzusisiz ham o'tkazadi)."""
    from app.services import telegram_user as tg

    items: list[RawItem] = []
    seen: set[str] = set()
    # Yangilari birinchi — takrorlarda eng yangisi qoladi
    for m in sorted(messages, key=lambda x: x.date or datetime.min.replace(tzinfo=UTC), reverse=True):
        hits, snippet = _match_snippet(m.text, patterns)
        if patterns and not hits and not global_scope:
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
            scope="regional" if global_scope and hits else None,
            # "leak" chatidagi mintaqaga oid bo'lmagan suhbat — kategoriyani klassifikator beradi (🔔 oqimi bo'lmasin)
            ignore_source_category=global_scope and not hits,
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
        last_id = 0 if ctx.dry_run else int((ctx.source.state or {}).get("last_id") or 0)
        try:
            if chat:
                messages = await tg.fetch_chat_messages(chat, settings.tg_messages_per_chat, min_id=last_id)
            else:
                messages = await tg.fetch_messages()
        except tg.TelegramNotConfigured as exc:
            raise AuthMissing(str(exc)) from exc
        except errors.FloodWaitError as exc:
            raise RateLimited(f"Telegram FloodWait {exc.seconds} s", retry_after=float(exc.seconds)) from exc
        except (ValueError, errors.RPCError) as exc:
            raise ConnectorError(f"Telegram: {type(exc).__name__}: {exc}") from exc
        # Bitta chat manbasida "leak" kategoriyasi manbaning o'zida (sources.category_id)
        leak_keys = [] if chat else settings.tg_leak_chats_list
        # Global manba: Markaziy Osiyo kalit so'zlari talab qilinmaydi (mavzu filtri — manbaning `cyber_filter`
        # bayrog'ida); kalit so'z topilgan xabar `regional` bo'ladi — asosiy lenta avvalgidek to'liq
        items = messages_to_items(messages, leak_keys, keyword_patterns(), global_scope=ctx.source.scope == "global")
        state = None
        if chat and messages and not ctx.dry_run:
            state = {**(ctx.source.state or {}), "last_id": max(m.msg_id for m in messages)}
        return FetchResult(items, None, state=state)
