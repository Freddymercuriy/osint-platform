"""Publisher fon vazifasi (API jarayoni ichida): rejalashtiruvchi (30 s), yuboruvchi (5 s), yangilanishlar (long poll).

O'z advisory lock'i (`LOCK_KEY`, yig'uvchinikidan boshqa) — bir nechta jarayonda faqat bittasi ishlaydi.
Token yo'q bo'lsa ham dry-run ishlaydi (Telegram'ga murojaat yo'q), `publisher_state.bot_status = missing`.
Ishga tushganda: `getMe` (401 — `invalid` + ogohlantirish), `getWebhookInfo` (webhook o'rnatilgan — boshqa tizim
botni ishlatayotgan bo'lishi mumkin: o'chirilmaydi, publisher pauzada + `webhook_conflict`).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import settings
from app.core.db import AsyncSessionLocal, engine
from app.services.publisher import planner, sender, updates
from app.services.publisher.bot import (
    BotClient,
    BotConflict,
    BotError,
    BotNetworkError,
    BotUnauthorized,
    make_client,
    redact,
    token_configured,
)
from app.services.publisher.outbox import get_state

log = logging.getLogger("osint.publisher")

LOCK_KEY = 72_620_261_115  # pg_advisory_lock kaliti (scheduler.LOCK_KEY dan farqli)
PLAN_EVERY = 30.0
SEND_EVERY = 5.0


@dataclass
class RunnerState:
    running: bool = False
    lock_held: bool = False
    last_plan: datetime | None = None
    last_send: datetime | None = None
    last_error: str | None = None
    _task: asyncio.Task | None = field(default=None, repr=False)


state = RunnerState()


async def check_bot(client: BotClient) -> str:
    """Bot holati (bazaga yoziladi): ok | invalid (401) | conflict (webhook o'rnatilgan) | error (tarmoq)."""
    async with AsyncSessionLocal() as db:
        st = await get_state(db)
        try:
            me = await client.get_me()
            st.bot_id, st.bot_username = me.get("id"), me.get("username")
            info = await client.get_webhook_info()
            if info.get("url"):
                status = "conflict"
                await sender.raise_alert(db, "webhook_conflict", {"bot": st.bot_username})
            else:
                status = "ok"
                await sender.resolve_alerts(db, "webhook_conflict")
                await sender.resolve_alerts(db, "bot_token_invalid")
        except BotUnauthorized as exc:
            status, st.last_error = "invalid", redact(str(exc))[:500]
            await sender.raise_alert(db, "bot_token_invalid", {"error": st.last_error[:300]})
        except BotError as exc:
            status, st.last_error = "error", redact(str(exc))[:500]
        st.bot_status, st.bot_checked_at = status, datetime.now(UTC)
        await db.commit()
        return status


async def _set_status(status: str) -> None:
    async with AsyncSessionLocal() as db:
        st = await get_state(db)
        st.bot_status, st.bot_checked_at = status, datetime.now(UTC)
        await db.commit()


async def _poll_loop(client: BotClient) -> None:
    delay = 5.0
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await updates.poll_once(db, client)
            delay = 5.0
        except asyncio.CancelledError:
            raise
        except BotConflict as exc:
            log.warning("getUpdates: konflikt (webhook yoki boshqa poller) — %s", exc)
            async with AsyncSessionLocal() as db:
                await sender.raise_alert(db, "webhook_conflict", {"error": redact(str(exc))[:300]})
                await db.commit()
            await asyncio.sleep(60)
        except BotUnauthorized:
            await _set_status("invalid")
            return
        except BotNetworkError as exc:
            log.info("getUpdates: tarmoq xatosi — %s; %.0f s dan keyin", exc, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 120.0)
        except Exception:
            log.exception("getUpdates xatosi")
            await asyncio.sleep(15)


async def _work(client: BotClient | None) -> None:
    loop = asyncio.get_running_loop()
    next_plan = 0.0
    while True:
        if loop.time() >= next_plan:
            next_plan = loop.time() + PLAN_EVERY
            try:
                async with AsyncSessionLocal() as db:
                    stats = await planner.plan(db)
                state.last_plan = datetime.now(UTC)
                if stats.created:
                    log.info("Publisher: %d ta post rejalashtirildi %s", stats.created, stats.by_status)
            except Exception as exc:
                state.last_error = redact(str(exc))[:300]
                log.exception("Publisher rejalashtiruvchi xatosi")
        if client is not None:
            try:
                async with AsyncSessionLocal() as db:
                    s = await sender.send_due(db, client)
                state.last_send = datetime.now(UTC)
                if s.sent or s.failed:
                    log.info("Publisher: yuborildi %d, xato %d", s.sent, s.failed)
            except Exception as exc:
                state.last_error = redact(str(exc))[:300]
                log.exception("Publisher yuboruvchi xatosi")
        await asyncio.sleep(SEND_EVERY)


async def _try_lock(conn: AsyncConnection) -> bool:
    got = (await conn.execute(text("select pg_try_advisory_lock(:k)"), {"k": LOCK_KEY})).scalar()
    await conn.commit()
    return bool(got)


async def _loop() -> None:
    state.running = True
    await asyncio.sleep(5)  # ilova va yig'uvchi ishga tushsin
    lock_conn: AsyncConnection | None = None
    client: BotClient | None = None
    poll: asyncio.Task | None = None
    try:
        while lock_conn is None:
            conn = await engine.connect()
            if await _try_lock(conn):
                lock_conn = conn
            else:
                await conn.close()
                log.info("Publisher boshqa jarayonda ishlayapti — 60 s kutamiz")
                await asyncio.sleep(60)
        state.lock_held = True
        async with AsyncSessionLocal() as db:
            if n := await sender.recover_sending(db):
                log.warning("Publisher: %d ta post 'sending' da qolgan edi — 'unknown' qilindi", n)
        if token_configured():
            client = make_client()
            status = await check_bot(client)
            if status in ("invalid", "conflict"):
                log.warning("Publisher: bot holati %s — yuborish to'xtatildi (dry-run ishlaydi)", status)
                await client.aclose()
                client = None
            else:
                poll = asyncio.create_task(_poll_loop(client), name="publisher-updates")
        else:
            await _set_status("missing")
        log.info("Publisher ishga tushdi (bot: %s)", "bor" if client else "yo'q — faqat dry-run")
        await _work(client)
    except asyncio.CancelledError:
        raise
    finally:
        if poll:
            poll.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await poll
        if client:
            await client.aclose()
        if lock_conn is not None:
            with contextlib.suppress(Exception):
                await lock_conn.execute(text("select pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
                await lock_conn.close()
        state.running = state.lock_held = False


async def _supervise() -> None:
    """Kutilmagan xato vazifani jimgina to'xtatmasin: logga yoziladi va 60 s dan keyin qayta ishga tushadi."""
    while True:
        try:
            await _loop()
            return
        except asyncio.CancelledError:
            return
        except Exception as exc:
            state.last_error = redact(str(exc))[:300]
            log.exception("Publisher to'xtadi — 60 s dan keyin qayta ishga tushadi")
            await asyncio.sleep(60)


def start() -> None:
    if settings.publisher_enabled and state._task is None:
        state._task = asyncio.create_task(_supervise(), name="publisher")


async def stop() -> None:
    if state._task:
        state._task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):  # o'chishni vazifaning eski xatosi to'xtatmasin
            await state._task
        state._task = None
