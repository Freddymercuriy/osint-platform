"""Telegram "Arxiv" papkasidagi kanal va guruhlar → alohida manbalar (`TG_MONITOR_ARCHIVED=true`).

- Har arxivlangan kanal/guruh uchun `telegram_user` manbasi (config {"chat": username yoki -100id}) bir marta
  yaratiladi — 0006 migratsiyasidagi TG_CHATS manbalari bilan bir xil sozlama (10 daqiqa, ochiq kanal — tarjima
  yoqiq, yopiq chat — o'chiq: yopiq guruh matni tarjima servisiga faqat admin ruxsat bersa yuboriladi).
- Shu chat (username yoki ID) bilan manba allaqachon bo'lsa — tegilmaydi, o'chirib qo'yilgan (disabled) bo'lsa ham.
  Butunlay o'chirilgan manba keyingi tekshiruvda qayta yaratiladi — kerak bo'lmasa o'chirish o'rniga "disable".
- Arxivdan chiqarilgan chat manbasi qoladi (asosiy ro'yxatdan ham o'qiladi).
- Housekeeping'dan: muvaffaqiyatli tekshiruvdan keyin soatda bir marta (Telegram limitlari); sessiya yo'q yoki
  bekor bo'lsa — keyingi housekeeping'da (10 daqiqa) yana urinadi.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.models import Source

log = logging.getLogger("osint.telegram")

SYNC_EVERY = 3600
INTERVAL = 600
_last_ok: float = 0.0


def _norm(value: object) -> str:
    return str(value or "").strip().lstrip("@").lower()


def _source_name(title: str, key: str) -> str:
    suffix = f" [{key}]"
    room = 128 - len("Telegram: ") - len(suffix)
    return f"Telegram: {title.strip()[:room]}{suffix}"


async def sync_archived_sources(db, chats, now: datetime | None = None) -> list[Source]:
    """`chats` (arxivdagi ChatInfo'lar) dan hali manbasi yo'qlari uchun manba yaratadi; yangilarini qaytaradi."""
    from app.services.events.scheduler import initial_offset

    now = now or datetime.now(UTC)
    rows = (await db.execute(select(Source.name, Source.config).where(Source.kind == "telegram_user"))).all()
    known = {_norm((cfg or {}).get("chat")) for _, cfg in rows} - {""}
    names = {name for name, _ in rows}
    created: list[Source] = []
    for c in chats:
        key = c.username or str(c.id)
        if {_norm(key), str(c.id), _norm(c.username)} & known:
            continue
        name = _source_name(c.title, key)
        if name in names:
            continue
        src = Source(
            name=name, kind="telegram_user", config={"chat": key}, lang="uz", scope="regional",
            translate=bool(c.username), enabled=True, interval_seconds=INTERVAL, jitter_pct=20, backfill_days=14,
            notes=f"Telegram arxividan avtomatik ({'kanal' if c.kind == 'channel' else 'guruh'})",
            state={"origin": "archive"}, status="never_run",
            next_run_at=now + timedelta(seconds=initial_offset(INTERVAL)),
        )
        db.add(src)
        created.append(src)
        known.add(_norm(key))
        names.add(name)
    if created:
        await db.commit()
    return created


async def maybe_sync() -> int:
    """Housekeeping'dan chaqiriladi. Yangi yaratilgan manbalar soni."""
    global _last_ok
    from telethon import errors

    from app.services import telegram_user as tg

    if not settings.tg_monitor_archived or not tg.is_configured() or not tg.session_exists():
        return 0
    if _last_ok and time.monotonic() - _last_ok < SYNC_EVERY:
        return 0
    try:
        chats = await tg.list_archived_chats()
    except tg.TelegramNotConfigured:
        return 0  # sessiya bekor — tg_login.py dan keyin o'zi davom etadi
    except errors.RPCError as exc:
        log.warning("Telegram arxivini o'qib bo'lmadi: %s", type(exc).__name__)
        return 0
    async with AsyncSessionLocal() as db:
        created = await sync_archived_sources(db, chats)
    _last_ok = time.monotonic()
    if created:
        log.info("Telegram arxividan %d ta yangi manba: %s", len(created), ", ".join(s.name for s in created[:10]))
    return len(created)
