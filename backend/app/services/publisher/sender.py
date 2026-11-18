"""Yuboruvchi: `queued` postlar → Telegram (Bot API), ustuvorlik tartibida, chat bo'yicha ≥ 1,1 s va ≤ 18 ta/daqiqa.

Holatlar: yuborishdan oldin `sending` (commit), keyin `sent` + `message_id`. Ishga tushganda `sending` da qolgani —
`unknown` va admin ogohlantirishi (rahbariyat oldida takror xabar — bo'shliqdan yomonroq; admin kanalni tekshiradi).
Xatolar:
- 429 — `retry_after` kutiladi (post `queued` da qoladi);
- 400 parse xatosi — bir marta oddiy matn sifatida (meta'da belgi — shablon xatosi tuzatilishi kerak);
- 403 / chat topilmadi — kanal `down`, ogohlantirish `channel_down`, shu kanalga yuborish to'xtaydi;
- 401 — bot `invalid`, hamma yuborish to'xtaydi, ogohlantirish `bot_token_invalid`;
- tarmoq — eksponensial kutish + jitter; boshqa 400 — `failed`.
Tezkor xabar yig'ilganidan 6 soat ichida yuborilmasa — `expired`.
Xato matnlari `bot.redact` dan o'tgan (token hech qayerga yozilmaydi).
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminAlert, ChannelDestination, ChannelPost
from app.services.publisher.bot import (
    BotBadRequest,
    BotClient,
    BotError,
    BotForbidden,
    BotNetworkError,
    BotRateLimited,
    BotUnauthorized,
    redact,
)
from app.services.publisher.outbox import get_state
from app.services.publisher.planner import EXPIRE
from app.services.publisher.render import plain

log = logging.getLogger("osint.publisher")

MIN_GAP = 1.1  # bitta chatga ketma-ket xabarlar orasida, soniya
PER_MINUTE = 18
MAX_BACKOFF = 600


@dataclass
class RateState:
    last: dict[int, float] = field(default_factory=dict)
    window: dict[int, deque] = field(default_factory=dict)

    def delay(self, chat_id: int, now: float) -> float:
        wait = 0.0
        if chat_id in self.last:
            wait = max(wait, self.last[chat_id] + MIN_GAP - now)
        win = self.window.setdefault(chat_id, deque())
        while win and win[0] <= now - 60:
            win.popleft()
        if len(win) >= PER_MINUTE:
            wait = max(wait, win[0] + 60 - now)
        return max(0.0, wait)

    def mark(self, chat_id: int, now: float) -> None:
        self.last[chat_id] = now
        self.window.setdefault(chat_id, deque()).append(now)


rate = RateState()


@dataclass
class SendStats:
    sent: int = 0
    failed: int = 0
    expired: int = 0
    stopped: str | None = None


# --------------------------------------------------------------------------- ogohlantirishlar
async def raise_alert(db: AsyncSession, kind: str, data: dict, *, key: int | None = None) -> None:
    """Ochiq ogohlantirish bo'lmasa — yangisi (`key` — kanal yoki post id, bir xil turdagi takrorni oldini oladi)."""
    stmt = select(AdminAlert.id).where(AdminAlert.kind == kind, AdminAlert.resolved_at.is_(None))
    if key is not None:
        stmt = stmt.where(AdminAlert.data["key"].as_integer() == key)
    if await db.scalar(stmt.limit(1)):
        return
    db.add(AdminAlert(kind=kind, data={**data, **({"key": key} if key is not None else {})}))


async def resolve_alerts(db: AsyncSession, kind: str, key: int | None = None, now: datetime | None = None) -> None:
    rows = (await db.scalars(select(AdminAlert).where(AdminAlert.kind == kind, AdminAlert.resolved_at.is_(None)))).all()
    for a in rows:
        if key is None or (a.data or {}).get("key") == key:
            a.resolved_at = now or datetime.now(UTC)


async def mark_down(db: AsyncSession, d: ChannelDestination, error: str, now: datetime) -> None:
    if d.status != "down":
        d.down_since = now
    d.status, d.last_error = "down", error[:500]
    d.consecutive_failures += 1
    await raise_alert(db, "channel_down", {"destination": d.name, "error": error[:300]}, key=d.id)


async def mark_up(db: AsyncSession, d: ChannelDestination, now: datetime) -> None:
    d.status, d.down_since, d.consecutive_failures = "ok", None, 0
    d.last_success_at = now
    await resolve_alerts(db, "channel_down", d.id, now)


# --------------------------------------------------------------------------- tiklanish
async def recover_sending(db: AsyncSession) -> int:
    """Ishga tushganda: `sending` da qolgan postlar → `unknown` + ogohlantirish (yuborilganmi — noma'lum)."""
    rows = (await db.scalars(select(ChannelPost).where(ChannelPost.status == "sending"))).all()
    for p in rows:
        p.status = "unknown"
        p.last_error = "Jarayon yuborish paytida to'xtadi — kanalda bor-yo'qligini tekshiring"
        await raise_alert(db, "post_unknown", {"post_id": p.id, "destination_id": p.destination_id}, key=p.id)
    await db.commit()
    return len(rows)


# --------------------------------------------------------------------------- yuborish
def _markup(buttons: list) -> dict | None:
    rows = [[b for b in row if isinstance(b, dict) and b.get("text") and b.get("url")] for row in buttons or []]
    rows = [r for r in rows if r]
    return {"inline_keyboard": rows} if rows else None


async def _send(client: BotClient, d: ChannelDestination, p: ChannelPost, text: str, reply_to: int | None,
                markup: dict | None, *, parse_mode: str | None, photo: bytes | None):
    if photo is not None:
        return await client.send_photo(d.chat_id, photo, caption=text, parse_mode=parse_mode, silent=p.silent,
                                       protect_content=d.protect_content, reply_markup=markup, thread_id=d.topic_id,
                                       reply_to=reply_to, filename=f"news-{(p.event_ids or [p.id])[0]}.jpg",
                                       content_type="image/jpeg")
    return await client.send_message(d.chat_id, text, parse_mode=parse_mode, silent=p.silent,
                                     protect_content=d.protect_content, reply_to=reply_to, reply_markup=markup,
                                     thread_id=d.topic_id)


def _fallback_photo(p: ChannelPost) -> bytes:
    from app.services.media import art, store

    return store.encode(art.render_fallback(str((p.meta or {}).get("rubric") or "cyber")))[0]


async def _deliver(client: BotClient, d: ChannelDestination, p: ChannelPost, reply_to: int | None):
    """Rasmli post — sendPhoto (izoh), aks holda sendMessage. HTML xatosi — oddiy matn; Telegram rasmni rad etsa —
    bir marta zaxira rasm bilan (post rasmsiz chiqmasin)."""
    text = p.final_text
    markup = _markup(p.buttons)
    photo = bytes(p.photo) if p.photo else None
    try:
        return await _send(client, d, p, text, reply_to, markup, parse_mode="HTML", photo=photo)
    except BotBadRequest as exc:
        if photo is not None and exc.photo_rejected:
            log.error("Post %s: Telegram rasmni qabul qilmadi (%s) — zaxira rasm bilan qayta", p.id, exc)
            p.meta = {**(p.meta or {}), "photo_error": str(exc)[:300], "photo_fallback": True}
            return await _send(client, d, p, text, reply_to, markup, parse_mode="HTML", photo=_fallback_photo(p))
        if not exc.is_parse_error:
            raise
        log.error("Post %s: HTML parse xatosi (%s) — oddiy matn sifatida qayta yuboriladi", p.id, exc)
        p.meta = {**(p.meta or {}), "parse_error": str(exc)[:300], "sent_plain": True}
        return await _send(client, d, p, plain(text), reply_to, markup, parse_mode=None, photo=photo)


async def send_due(db: AsyncSession, client: BotClient, now: datetime | None = None, *, max_posts: int = 10,
                   sleep: Callable[[float], Awaitable] = asyncio.sleep,
                   clock: Callable[[], float] = time.monotonic) -> SendStats:
    stats = SendStats()
    now = now or datetime.now(UTC)
    st = await get_state(db)
    if st.paused or st.bot_status in ("invalid", "conflict"):
        stats.stopped = "paused" if st.paused else st.bot_status
        await db.commit()
        return stats
    rows = (await db.execute(
        select(ChannelPost, ChannelDestination)
        .join(ChannelDestination, ChannelDestination.id == ChannelPost.destination_id)
        .where(ChannelPost.status == "queued",
               (ChannelPost.scheduled_at.is_(None)) | (ChannelPost.scheduled_at <= now),
               (ChannelPost.next_attempt_at.is_(None)) | (ChannelPost.next_attempt_at <= now),
               ChannelDestination.enabled.is_(True), ChannelDestination.paused.is_(False),
               ChannelDestination.mode != "dry_run", ChannelDestination.chat_id.is_not(None),
               ChannelDestination.status != "down")
        .order_by(ChannelPost.priority.desc().nulls_last(), ChannelPost.created_at, ChannelPost.id)
        .limit(max_posts)
        .execution_options(populate_existing=True)  # boshqa jarayon (CLI) o'zgartirgan holat — xotiradagi emas
    )).all()
    blocked: set[int] = set()  # shu tsiklda to'xtatilgan kanallar (429, down)
    for p, d in rows:
        if d.id in blocked:
            continue
        now = datetime.now(UTC) if stats.sent else now
        if p.kind in ("alert", "followup") and p.created_at and p.created_at < now - EXPIRE:
            p.status, p.skip_reason = "expired", "stale"
            stats.expired += 1
            await db.commit()
            continue
        if p.kind == "followup":  # davom xabari — faqat asl rasmli post chiqqandan keyin, unga javob sifatida
            parent = await db.get(ChannelPost, p.reply_to_post_id) if p.reply_to_post_id else None
            if parent is None or parent.status in ("failed", "expired", "skipped", "rejected"):
                p.status, p.skip_reason = "skipped", "parent_not_sent"
                await db.commit()
                continue
            if parent.status != "sent":
                continue
        wait = rate.delay(d.chat_id, clock())
        if wait > 0:
            await sleep(wait)
        reply_to = None
        if p.reply_to_post_id:
            parent = await db.get(ChannelPost, p.reply_to_post_id)
            reply_to = parent.message_id if parent else None
        p.status, p.attempts = "sending", p.attempts + 1
        await db.commit()
        try:
            msg = await _deliver(client, d, p, reply_to)
        except BotRateLimited as exc:
            p.status, p.next_attempt_at = "queued", datetime.now(UTC) + timedelta(seconds=exc.retry_after or 30)
            p.last_error = redact(str(exc))[:500]
            blocked.add(d.id)
            stats.stopped = "rate_limited"
        except BotUnauthorized as exc:
            p.status, p.last_error = "queued", redact(str(exc))[:500]
            st.bot_status, st.last_error = "invalid", redact(str(exc))[:500]
            await raise_alert(db, "bot_token_invalid", {"error": redact(str(exc))[:300]})
            await db.commit()
            stats.stopped = "unauthorized"
            break
        except (BotForbidden, BotBadRequest) as exc:
            err = redact(str(exc))[:500]
            if isinstance(exc, BotForbidden) or exc.chat_not_found:
                p.status, p.last_error = "queued", err  # kanal tiklansa yuboriladi (yoki 6 soatda eskiradi)
                await mark_down(db, d, err, datetime.now(UTC))
                blocked.add(d.id)
            else:
                p.status, p.last_error = "failed", err
                stats.failed += 1
        except BotNetworkError as exc:
            delay = min(MAX_BACKOFF, 5 * 2 ** min(p.attempts, 7)) + random.uniform(0, 3)
            p.status, p.next_attempt_at = "queued", datetime.now(UTC) + timedelta(seconds=delay)
            p.last_error = redact(str(exc))[:500]
            blocked.add(d.id)
        except BotError as exc:
            p.status, p.last_error = "failed", redact(str(exc))[:500]
            stats.failed += 1
        else:
            rate.mark(d.chat_id, clock())
            sent_at = datetime.now(UTC)
            p.status, p.sent_at, p.message_id, p.chat_id = "sent", sent_at, msg.message_id, msg.chat_id
            p.last_error, p.next_attempt_at = None, None
            if "<b>" in p.final_text and not msg.entities and not (p.meta or {}).get("sent_plain"):
                p.meta = {**(p.meta or {}), "entities_missing": True}
                log.warning("Post %s: Telegram formatlashni tanimadi (entities bo'sh)", p.id)
            await mark_up(db, d, sent_at)
            stats.sent += 1
        await db.commit()
    return stats
