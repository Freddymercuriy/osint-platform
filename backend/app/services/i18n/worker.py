"""Tarjima navbati: har hodisa uchun en / ru / uz qatorlari va ularni to'ldirish.

1. `ensure_rows` — tarjima qatorlari yo'q hodisalar uchun reja: asl til (aniqlangan) — nusxa; o'zbek kirill — lotinga
   transliteratsiya; tuzilgan elementlar sarlavhasi — shablon (`templates.py`); qolgani — `pending` (yoki manba
   tarjimaga ruxsat bermasa `skipped`).
2. `process_pending` — navbatni jiddiylik bo'yicha (avval critical), paketlab tarjima qiladi: avval kesh, keyin
   provayder (o'z NLLB servisi); oylik belgi chegarasi (0 — chegarasiz); xatoda qator `pending` da qoladi va qayta
   urinadi (3 marta, hodisa shu orada asl tilda ko'rsatiladi), 422 / noma'lum tilda — darhol `failed`; rate limitda kutish.
Sarlavha 300, matn 600 belgigacha qisqartiriladi.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import EventRecord, EventTranslation, Source, TranslationCache, TranslationUsage
from app.models.category import SEVERITIES
from app.services.connectors.base import AuthMissing, ConnectorError, RateLimited
from app.services.i18n.templates import render_title
from app.services.i18n.text import LANGS, detect_lang, is_cyrillic, normalize_uz, uz_to_latin
from app.services.i18n.translator import (
    MAX_CHARS,
    MAX_STRINGS,
    TranslationRequestError,
    Translator,
    UnsupportedLanguage,
)

log = logging.getLogger("osint.i18n")

TITLE_MAX = 300
SUMMARY_MAX = 600
MAX_ATTEMPTS = 3


@dataclass
class WorkerState:
    last_run: datetime | None = None
    last_error: str | None = None
    budget_exhausted: bool = False
    key_rejected: bool = False
    translated_total: int = 0
    paused_until: datetime | None = None


state = WorkerState()


def clip(text: str | None, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def cache_key(source: str, target: str, text: str) -> str:
    return hashlib.sha256(f"{source}|{target}|{text}".encode()).hexdigest()


def month_start(now: datetime | None = None) -> date:
    d = (now or datetime.now(UTC)).date()
    return d.replace(day=1)


def _fix_uz(text: str) -> str:
    """Provayder o'zbekchani kirillda qaytarsa — lotinga (latin.jaybi.uz dvigateli); apostroflar bir xil."""
    return normalize_uz(uz_to_latin(text) if is_cyrillic(text) else text)


# ---------------------------------------------------------------- reja
def plan_rows(ev: EventRecord, allow_mt: bool, now: datetime) -> list[EventTranslation]:
    """Hodisa uchun en/ru/uz qatorlari. `ev.lang` aniqlangan tilga yangilanadi (asli `extra.feed_lang`)."""
    detected = detect_lang(f"{ev.title} {ev.summary}", fallback=ev.lang or "en")
    if detected != ev.lang:
        ev.extra = {**(ev.extra or {}), "feed_lang": ev.lang}
        ev.lang = detected
    cyr_uz = detected == "uz" and is_cyrillic(ev.title)
    templ = render_title(ev.extra or {}, ev.countries or [], ev.category)
    has_summary = bool((ev.summary or "").strip())
    rows: list[EventTranslation] = []
    for lang in LANGS:
        t_title = clip(templ[lang], TITLE_MAX) if templ else None
        if lang == detected:
            if cyr_uz:
                title, summary, provider = uz_to_latin(ev.title), uz_to_latin(ev.summary or ""), "translit"
            elif lang == "uz":
                title, summary, provider = normalize_uz(ev.title), normalize_uz(ev.summary or ""), "source"
            else:
                title, summary, provider = ev.title, ev.summary or "", "source"
            rows.append(EventTranslation(event_id=ev.id, lang=lang, title=t_title or title, summary=summary,
                                         provider="template" if t_title and provider == "source" else provider,
                                         status="done", translated_at=now))
            continue
        if t_title and not has_summary:
            rows.append(EventTranslation(event_id=ev.id, lang=lang, title=t_title, summary="", provider="template",
                                         status="done", translated_at=now))
        elif not allow_mt:
            rows.append(EventTranslation(event_id=ev.id, lang=lang, title=t_title, summary=None, provider="none",
                                         status="skipped", error="Manba tarjimaga ruxsat bermagan (translate=false)"))
        else:
            # null maydonlar — tarjima qilinadi; shablon sarlavha tayyor bo'lsa faqat matn
            rows.append(EventTranslation(event_id=ev.id, lang=lang, title=t_title,
                                         summary=None if has_summary else "",
                                         provider="template" if t_title else "none", status="pending"))
    return rows


async def ensure_rows(db: AsyncSession, limit: int = 300) -> int:
    """Tarjima qatorlari yo'q hodisalar uchun rejani yozadi (yangi hodisalar va eski bazani to'ldirish)."""
    has = select(EventTranslation.id).where(EventTranslation.event_id == EventRecord.id).exists()
    events = (await db.scalars(
        select(EventRecord).where(~has).order_by(EventRecord.id.desc()).limit(limit)
    )).all()
    if not events:
        return 0
    allow = dict((await db.execute(select(Source.id, Source.translate))).all())
    now = datetime.now(UTC)
    for ev in events:
        allow_mt = settings.translate_enabled and allow.get(ev.source_id, True)
        db.add_all(plan_rows(ev, allow_mt, now))
    await db.commit()
    return len(events)


# ---------------------------------------------------------------- navbat
@dataclass
class ProcessStats:
    rows: int = 0
    done: int = 0
    from_cache: int = 0
    chars_sent: int = 0
    requests: int = 0
    failed: int = 0
    stopped: str | None = None
    errors: list[str] = field(default_factory=list)
    done_event_ids: set[int] = field(default_factory=set)  # tarjimasi tugagan hodisalar (ustuvorlik qayta hisoblanadi)


async def usage_row(db: AsyncSession, now: datetime | None = None) -> TranslationUsage:
    m = month_start(now)
    row = await db.get(TranslationUsage, m)
    if row is None:
        row = TranslationUsage(month=m, chars=0, requests=0)
        db.add(row)
        await db.flush()
    return row


def _severity_rank():
    return case(*((EventRecord.severity == s, i) for i, s in enumerate(SEVERITIES)), else_=0)


async def process_pending(db: AsyncSession, translator: Translator, limit: int = 120) -> ProcessStats:
    stats = ProcessStats()
    now = datetime.now(UTC)
    if not translator.configured:
        stats.stopped = "no_key"
        return stats
    if state.paused_until and state.paused_until > now:
        stats.stopped = "paused"
        return stats
    usage = await usage_row(db, now)
    cap = settings.translate_monthly_char_limit  # 0 — chegarasiz
    state.budget_exhausted = cap > 0 and usage.chars >= cap
    if state.budget_exhausted:
        stats.stopped = "budget"
        await db.commit()
        return stats

    rows = (await db.execute(
        select(EventTranslation, EventRecord)
        .join(EventRecord, EventRecord.id == EventTranslation.event_id)
        .where(EventTranslation.status == "pending",
               (EventTranslation.next_attempt_at.is_(None)) | (EventTranslation.next_attempt_at <= now))
        .order_by(_severity_rank().desc(), EventRecord.first_seen.desc(), EventTranslation.id)
        .limit(limit)
    )).all()
    stats.rows = len(rows)
    # (manba til, maqsad til) bo'yicha guruhlash; har qatorning tarjima qilinadigan maydonlari
    groups: dict[tuple[str, str], list[tuple[EventTranslation, str, str]]] = defaultdict(list)
    for tr, ev in rows:
        src = ev.lang or "en"
        if tr.title is None:
            groups[(src, tr.lang)].append((tr, "title", clip(ev.title, TITLE_MAX)))
        if tr.summary is None:
            groups[(src, tr.lang)].append((tr, "summary", clip(ev.summary, SUMMARY_MAX)))

    for (src, tgt), fields in groups.items():
        # kesh
        keys = {cache_key(src, tgt, text) for _, _, text in fields}
        cached = dict((await db.execute(
            select(TranslationCache.key, TranslationCache.text).where(TranslationCache.key.in_(keys))
        )).all())
        todo: list[tuple[EventTranslation, str, str]] = []
        for tr, fld, text in fields:
            k = cache_key(src, tgt, text)
            if not text:
                setattr(tr, fld, "")
            elif k in cached:
                setattr(tr, fld, cached[k])
                stats.from_cache += 1
                tr.provider = "cache" if tr.provider == "none" else tr.provider
            else:
                todo.append((tr, fld, text))
        # provayder — paketlar (≤64 satr, ≤12k belgi; uzun matnlarni klient o'zi bo'ladi); takror matnlar bir marta
        unique: list[str] = list(dict.fromkeys(t for _, _, t in todo))
        results: dict[str, str] = {}
        errors: dict[str, tuple[str, bool]] = {}  # matn → (xato, qayta urinish befoyda)
        i = 0
        while i < len(unique):
            batch, size = [], 0
            while i < len(unique) and len(batch) < MAX_STRINGS and size + len(unique[i]) <= MAX_CHARS:
                batch.append(unique[i])
                size += len(unique[i])
                i += 1
            if not batch:  # bitta matn ham sig'madi (bo'lmasligi kerak — qisqartirilgan)
                batch, size = [unique[i][:MAX_CHARS]], min(len(unique[i]), MAX_CHARS)
                i += 1
            if cap > 0 and usage.chars + size > cap:
                state.budget_exhausted = True
                stats.stopped = "budget"
                break
            try:
                out = await translator.translate(batch, src, tgt)
            except AuthMissing as exc:
                state.key_rejected, state.last_error = True, str(exc)
                state.paused_until = now + timedelta(hours=1)
                stats.stopped, stats.errors = "auth", [str(exc)]
                break
            except RateLimited as exc:
                state.last_error = str(exc)
                state.paused_until = now + timedelta(seconds=exc.retry_after or 600)
                stats.stopped, stats.errors = "rate_limited", [str(exc)]
                break
            except ConnectorError as exc:
                permanent = isinstance(exc, (TranslationRequestError, UnsupportedLanguage))
                log.warning("Tarjima %s→%s (%d ta matn) bajarilmadi%s: %s", src, tgt, len(batch),
                            "" if permanent else " — keyinroq qayta urinadi", exc)
                stats.errors.append(str(exc))
                state.last_error = str(exc)
                for t in batch:
                    results[t] = None  # type: ignore[assignment]
                    errors[t] = (str(exc), permanent)
                continue
            state.key_rejected = False
            usage.chars += size
            usage.requests += 1
            stats.chars_sent += size
            stats.requests += 1
            for text, translated in zip(batch, out, strict=True):
                translated = _fix_uz(translated) if tgt == "uz" else translated
                results[text] = translated
                db.add(TranslationCache(key=cache_key(src, tgt, text), source_lang=src, target_lang=tgt,
                                        text=translated, chars=len(text)))
        failed_rows: dict[int, tuple[EventTranslation, str, bool]] = {}
        for tr, fld, text in todo:
            if text in results and results[text] is not None:
                setattr(tr, fld, results[text])
                tr.provider = translator.name if tr.provider in ("none", "cache") else tr.provider
            elif text in results:  # provayder xatosi (qator bo'yicha bir marta hisoblanadi)
                failed_rows[id(tr)] = (tr, *errors.get(text, ("xato", False)))
        for tr, error, permanent in failed_rows.values():
            tr.attempts = MAX_ATTEMPTS if permanent else tr.attempts + 1
            tr.error = error[:500]
            if tr.attempts >= MAX_ATTEMPTS:
                tr.status = "failed"
                stats.failed += 1
            else:
                tr.next_attempt_at = now + timedelta(minutes=5 * 2 ** tr.attempts)
        if stats.stopped:
            break

    for tr, _ev in rows:
        if tr.status == "pending" and tr.title is not None and tr.summary is not None:
            tr.status, tr.translated_at, tr.error = "done", now, None
            stats.done += 1
            stats.done_event_ids.add(tr.event_id)
    state.translated_total += stats.done
    state.last_run = now
    await db.commit()
    return stats


async def retry_failed(db: AsyncSession) -> int:
    result = await db.execute(
        update(EventTranslation).where(EventTranslation.status == "failed")
        .values(status="pending", attempts=0, next_attempt_at=None, error=None)
    )
    await db.commit()
    state.paused_until = None
    return result.rowcount or 0


async def counts(db: AsyncSession) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for st, lang, n in (await db.execute(
        select(EventTranslation.status, EventTranslation.lang, func.count(EventTranslation.id))
        .group_by(EventTranslation.status, EventTranslation.lang)
    )).all():
        out[st][lang] = n
    return dict(out)
