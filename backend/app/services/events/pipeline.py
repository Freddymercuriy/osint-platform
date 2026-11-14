"""Ulagich qaytargan elementlarni bazaga yozish: tekshiruv → filtr → muddat → takror → yozish.

- URL faqat http(s) (lentadagi `javascript:` havola UI'da bosiladigan bo'lib qolmasligi uchun).
- `EVENTS_SINCE` dan oldingi va kategoriya saqlash muddatidan eski elementlar yozilmaydi.
- Manbaning birinchi muvaffaqiyatli yig'ishi — baseline: faqat `backfill_days` oynasidagi elementlar yoziladi,
  `is_baseline=True`, ogohlantirish bermaydi va "o'qilmagan" hisoblanmaydi.
- Takror: (1) `uid` — manba nomi + URL + sarlavha; (2) yangiliklar — sarlavha imzosi (`dedup.py`) 3 kunlik oynada;
  (3) manbalararo kalit (`dedup_key`, masalan ransomware qurboni). Takror topilsa yangi qator yozilmaydi —
  mavjud hodisaning `also_reported_by` ro'yxatiga manba qo'shiladi ("N ta manba xabar qildi").
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.i18n import DEFAULT_LANG, LANGS, t
from app.models import Category, EventRecord, Source, SourceRun, User
from app.models.category import SEVERITY_RANK
from app.services.connectors.base import RawItem
from app.services.connectors.google_news import GOOGLE_NEWS_TAG
from app.services.events.classifier import Classification, CompiledCategory, classify, compile_categories
from app.services.events.dedup import TitleSig, same_story, signature
from app.services.events.geo import detect_countries, detect_sector

log = logging.getLogger("osint.events")

DEDUP_CHANNELS = ("news",)
DEDUP_WINDOW = timedelta(days=3)  # shu oraliqdagi sarlavhalargina solishtiriladi
DEDUP_LOOKBACK = timedelta(days=14)  # bazadan qancha orqaga qarash
RUNS_KEEP = timedelta(days=30)

# Bir vaqtda faqat bitta manba natijasi yoziladi (takror tekshiruvi poygasiz bo'lishi uchun)
_WRITE_LOCK = asyncio.Lock()


def make_uid(source_name: str, url: str, title: str) -> str:
    return hashlib.sha256(f"{source_name}|{url}|{title}".encode()).hexdigest()


def valid_url(url: str) -> bool:
    try:
        parts = urlsplit((url or "").strip())
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def aware(when: datetime | None, default: datetime) -> datetime:
    if when is None:
        return default
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def categorize(item: RawItem, fixed: str | None, compiled: list[CompiledCategory],
               known: set[str]) -> tuple[str, Classification | None]:
    """Manbaning qat'iy kategoriyasi → ulagich bilgan kategoriya → qoidalar → `other`."""
    if fixed:
        return fixed, None
    if item.category and item.category in known:
        return item.category, None
    c = classify(item.title, item.summary, compiled)
    return c.slug, c


def retention_cutoff(category: Category | None, slug: str, now: datetime) -> datetime | None:
    """Shu vaqtdan eski hodisa saqlanmaydi. None — abadiy."""
    if category is not None:
        days = category.retention_days
    elif slug in settings.events_retention_keep_list:
        days = None
    else:
        days = settings.events_retention_days or None
    return now - timedelta(days=days) if days and days > 0 else None


def higher_severity(a: str | None, b: str | None) -> str:
    a, b = a or "info", b or "info"
    return a if SEVERITY_RANK.get(a, 0) >= SEVERITY_RANK.get(b, 0) else b


def _report(source: str, url: str, when: datetime) -> dict:
    return {"source": source, "url": url, "at": when.isoformat()}


def _add_report(rec: EventRecord, entry: dict) -> bool:
    if entry["source"] == rec.source or any(r.get("source") == entry["source"] for r in rec.also_reported_by or []):
        return False
    rec.also_reported_by = [*(rec.also_reported_by or []), entry]  # JSONB: yangi ro'yxat (o'zgarish kuzatilsin)
    return True


@dataclass
class StoreStats:
    received: int = 0
    invalid: int = 0
    expired: int = 0
    known: int = 0
    merged: int = 0
    new: int = 0
    records: list[EventRecord] = field(default_factory=list)


@dataclass
class _Prepared:
    item: RawItem
    uid: str
    display: str
    slug: str
    when: datetime
    old: bool  # backfill oynasidan eski — yoziladi, lekin ogohlantirish bermaydi
    fixed: bool = False  # kategoriya manba / ulagichdan (qayta tasniflashda o'zgarmaydi)
    classified: Classification | None = None


async def store_items(
    db: AsyncSession, source: Source, items: list[RawItem], now: datetime, *, baseline: bool
) -> StoreStats:
    stats = StoreStats(received=len(items))
    cats = {c.slug: c for c in (await db.scalars(select(Category))).all()}
    fixed = next((c for c in cats.values() if c.id == source.category_id), None) if source.category_id else None
    compiled = compile_categories(sorted(cats.values(), key=lambda c: c.sort_order))
    known = {slug for slug, c in cats.items() if c.enabled}
    since = settings.events_since_dt
    window = now - timedelta(days=max(0, source.backfill_days))
    if since and since > window:
        window = since

    prepared: list[_Prepared] = []
    for item in items:
        item.title = (item.title or "").strip()
        item.url = (item.url or "").strip()
        if not item.title or not valid_url(item.url):
            stats.invalid += 1
            continue
        slug, classified = categorize(item, fixed.slug if fixed else None, compiled, known)
        when = aware(item.published, now)
        if since and when < since:
            stats.expired += 1
            continue
        cutoff = retention_cutoff(cats.get(slug), slug, now)
        if cutoff and when < cutoff:
            stats.expired += 1
            continue
        old = item.published is not None and when < window
        if baseline and old:
            stats.expired += 1  # baseline: faqat backfill oynasi
            continue
        display = (item.source_name or source.name)[:128]
        prepared.append(_Prepared(item, make_uid(display, item.url, item.title), display, slug, when, old,
                                  fixed=classified is None, classified=classified))

    if not prepared:
        return stats

    async with _WRITE_LOCK:
        uids = {p.uid for p in prepared}
        existing = set((await db.scalars(select(EventRecord.uid).where(EventRecord.uid.in_(uids)))).all())
        if existing and source.id is not None:
            # Manbasi noma'lum eski yozuvlarni shu manbaga bog'laymiz (masalan v1 Telegram yozuvlari)
            await db.execute(update(EventRecord).where(
                EventRecord.uid.in_(existing), EventRecord.source_id.is_(None)
            ).values(source_id=source.id))
        fresh = [p for p in prepared if p.uid not in existing]
        stats.known = len(prepared) - len(fresh)
        # bitta paketdagi bir xil uid
        seen: set[str] = set()
        fresh = [p for p in fresh if not (p.uid in seen or seen.add(p.uid))]

        # Mavjud hodisalar: yangiliklar imzosi va manbalararo kalitlar
        known_news: list[tuple[TitleSig, datetime, EventRecord]] = []
        if any(p.item.channel in DEDUP_CHANNELS for p in fresh):
            rows = (await db.scalars(
                select(EventRecord).where(
                    EventRecord.channel.in_(DEDUP_CHANNELS),
                    EventRecord.first_seen >= now - DEDUP_LOOKBACK,
                )
            )).all()
            known_news = [(signature(r.title), aware(r.published or r.first_seen, now), r) for r in rows]
        keys = {p.item.dedup_key for p in fresh if p.item.dedup_key}
        by_key: dict[str, EventRecord] = {}
        if keys:
            rows = (await db.scalars(
                select(EventRecord).where(EventRecord.extra["dedup_key"].astext.in_(keys))
            )).all()
            by_key = {r.extra.get("dedup_key"): r for r in rows}

        # To'g'ridan-to'g'ri manba Google News nusxasidan, eski sana yangisidan ustun
        fresh.sort(key=lambda p: (GOOGLE_NEWS_TAG in p.display, p.when))
        for p in fresh:
            it = p.item
            entry = _report(p.display, it.url, p.when)
            if it.dedup_key and it.dedup_key in by_key:
                _add_report(by_key[it.dedup_key], entry)
                stats.merged += 1
                continue
            if it.channel in DEDUP_CHANNELS:
                sig = signature(it.title)
                match = next((r for s, w, r in known_news
                              if abs(p.when - w) <= DEDUP_WINDOW and same_story(sig, s)), None)
                if match is not None:
                    _add_report(match, entry)
                    stats.merged += 1
                    continue
            cat = cats.get(p.slug)
            if it.sector:
                it.sector = it.sector[:32]
            countries = it.countries or detect_countries(it.title, it.summary) or list(
                source.config.get("default_countries") or []
            )
            extra = dict(it.extra)
            if it.dedup_key:
                extra["dedup_key"] = it.dedup_key
            if p.fixed:
                extra["fixed_category"] = p.slug
            elif p.classified is not None:
                extra["classifier"] = {"score": p.classified.score, "hits": p.classified.hits}
            if it.severity:
                extra["severity_floor"] = it.severity
            rec = EventRecord(
                uid=p.uid, source=p.display, source_id=source.id, category=p.slug,
                category_id=cat.id if cat else None,
                title=it.title[:512], url=it.url[:1024], summary=it.summary or "",
                lang=(it.lang or source.lang or "en")[:8], published=it.published,
                channel=it.channel, scope=it.scope or source.scope,
                severity=higher_severity(cat.severity if cat else "info", it.severity),
                countries=countries[:5], sector=((it.sector or detect_sector(it.title, it.summary)) or None),
                actor=(it.actor or None) and it.actor[:128], matched_keywords=it.matched_keywords[:12],
                extra=extra, also_reported_by=[], is_baseline=baseline,
                notified=baseline or p.old,
            )
            db.add(rec)
            stats.records.append(rec)
            if it.channel in DEDUP_CHANNELS:
                known_news.append((signature(it.title), p.when, rec))
            if it.dedup_key:
                by_key[it.dedup_key] = rec
        await db.commit()
    stats.new = len(stats.records)
    return stats


# ---------------------------------------------------------------- tozalash
async def purge_expired(db: AsyncSession, now: datetime) -> int:
    """`EVENTS_SINCE` dan oldingi va kategoriya muddatidan eski hodisalar; 30 kundan eski source_runs."""
    when = func.coalesce(EventRecord.published, EventRecord.first_seen)
    purged = 0
    since = settings.events_since_dt
    if since is not None:
        purged += (await db.execute(delete(EventRecord).where(when < since))).rowcount or 0
    for cat in (await db.scalars(select(Category).where(Category.retention_days.is_not(None)))).all():
        if cat.retention_days and cat.retention_days > 0:
            purged += (await db.execute(delete(EventRecord).where(
                EventRecord.category_id == cat.id, when < now - timedelta(days=cat.retention_days)
            ))).rowcount or 0
    # Kategoriya yozuvi yo'q (v1 nomlari: news / telegram / tg_group) — muhitdagi umumiy muddat
    days = settings.events_retention_days
    if days and days > 0:
        stmt = delete(EventRecord).where(EventRecord.category_id.is_(None), when < now - timedelta(days=days))
        keep = settings.events_retention_keep_list
        if keep:
            stmt = stmt.where(EventRecord.category.notin_(keep))
        purged += (await db.execute(stmt)).rowcount or 0
    await db.execute(delete(SourceRun).where(SourceRun.started_at < now - RUNS_KEEP))
    await db.commit()
    return purged


# ---------------------------------------------------------------- Telegram "Saved Messages" ogohlantirishi (ixtiyoriy)
def format_alert(records: list[EventRecord], lang: str = "uz") -> str:
    icons = {"leak": "🟠", "ransomware": "🔴"}
    lines = [t("alert_header", lang, n=len(records)) + "\n"]
    for r in records[:10]:
        lines.append(f"{icons.get(r.category, '•')} [{r.category}] {r.source}\n{r.title[:200]}\n"
                     f"{r.summary[:250]}\n{r.url}\n")
    if len(records) > 10:
        lines.append(t("alert_more", lang, n=len(records) - 10))
    return "\n".join(lines)


async def _alert_lang(db: AsyncSession) -> str:
    """Ogohlantirish tili: birinchi adminning `users.locale`i (yo'q bo'lsa uz)."""
    loc = await db.scalar(select(User.locale).where(User.role == "admin").order_by(User.id).limit(1))
    return loc if loc in LANGS else DEFAULT_LANG


async def notify_new(db: AsyncSession, records: list[EventRecord]) -> int:
    """NOTIFY_TELEGRAM=true bo'lsa — ogohlantiriladigan kategoriyalardagi yangi (baseline emas) hodisalar."""
    if not settings.notify_telegram or not records:
        return 0
    notify_ids = set((await db.scalars(select(Category.id).where(Category.notify))).all())
    to_send = [r for r in records if not r.notified and r.category_id in notify_ids]
    if not to_send:
        return 0
    from app.services import telegram_user as tg

    if not tg.is_configured():
        return 0
    try:
        client = await tg.get_client()
        await client.send_message("me", format_alert(to_send, await _alert_lang(db)), link_preview=False)
    except Exception as exc:  # ogohlantirish yiqilsa ham yig'ish davom etadi
        log.warning("Telegram ogohlantirish yuborilmadi: %s", exc)
        return 0
    for r in to_send:
        r.notified = True
    await db.commit()
    return len(to_send)
