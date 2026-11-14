"""Kategoriyalar bilan ishlash: qayta tasniflash, o'chirishda hodisalarni `other` ga ko'chirish, jiddiylik."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, EventRecord, Source
from app.models.category import SEVERITIES, SEVERITY_RANK
from app.services.events.classifier import FALLBACK, classify, compile_categories


def effective_severity(category_severity: str, floor: str | None) -> str:
    if floor and SEVERITY_RANK.get(floor, 0) > SEVERITY_RANK.get(category_severity, 0):
        return floor
    return category_severity


def severity_sql(category_severity: str):
    """SQL: max(kategoriya jiddiyligi, extra.severity_floor)."""
    floor = EventRecord.extra["severity_floor"].astext
    rank = {s: i for i, s in enumerate(SEVERITIES)}
    floor_rank = case(*((floor == s, i) for s, i in rank.items()), else_=-1)
    return case((floor_rank > rank.get(category_severity, 0), floor), else_=category_severity)


@dataclass
class ReclassifyResult:
    considered: int = 0
    changed: int = 0
    severity_changed: int = 0
    locked_skipped: int = 0
    transitions: Counter = field(default_factory=Counter)
    samples: list[dict] = field(default_factory=list)


async def reclassify(db: AsyncSession, *, dry_run: bool = True, sample: int = 20) -> ReclassifyResult:
    """Qoidalarni saqlangan hodisalarga qo'llaydi. Qo'lda qo'yilgan (`category_locked`) kategoriyalar o'zgarmaydi;
    manba / ulagich bergan qat'iy kategoriya (`extra.fixed_category` yoki manbaning `category_id`) saqlanadi."""
    cats = list((await db.scalars(select(Category).order_by(Category.sort_order))).all())
    by_slug = {c.slug: c for c in cats}
    by_id = {c.id: c for c in cats}
    compiled = compile_categories(cats)
    source_fixed = dict((await db.execute(
        select(Source.id, Source.category_id).where(Source.category_id.is_not(None))
    )).all())
    res = ReclassifyResult()
    res.locked_skipped = await db.scalar(
        select(func.count(EventRecord.id)).where(EventRecord.category_locked)
    ) or 0
    rows = (await db.execute(
        select(EventRecord.id, EventRecord.title, EventRecord.summary, EventRecord.category, EventRecord.severity,
               EventRecord.source_id, EventRecord.extra)
        .where(EventRecord.category_locked.is_(False)).order_by(EventRecord.id)
    )).all()
    updates: list[dict] = []
    for r in rows:
        res.considered += 1
        extra = dict(r.extra or {})
        fixed = extra.get("fixed_category")
        if fixed in by_slug:
            target = by_slug[fixed]
        elif r.source_id in source_fixed and source_fixed[r.source_id] in by_id:
            target = by_id[source_fixed[r.source_id]]
        else:
            c = classify(r.title, r.summary, compiled)
            target = by_slug.get(c.slug) or by_slug[FALLBACK]
            extra["classifier"] = {"score": c.score, "hits": c.hits}
        sev = effective_severity(target.severity, extra.get("severity_floor"))
        if target.slug != r.category:
            res.changed += 1
            res.transitions[f"{r.category}→{target.slug}"] += 1
            if len(res.samples) < sample:
                res.samples.append({"id": r.id, "title": r.title[:160], "from": r.category, "to": target.slug})
        elif sev != r.severity:
            res.severity_changed += 1
        else:
            continue
        updates.append({"id": r.id, "category": target.slug, "category_id": target.id, "severity": sev,
                        "extra": extra})
    if not dry_run and updates:
        for u in updates:
            await db.execute(update(EventRecord).where(EventRecord.id == u["id"]).values(
                category=u["category"], category_id=u["category_id"], severity=u["severity"], extra=u["extra"],
            ))
        await db.commit()
    return res


async def move_events_to_other(db: AsyncSession, category: Category) -> int:
    other = await db.scalar(select(Category).where(Category.slug == FALLBACK))
    result = await db.execute(
        update(EventRecord).where(EventRecord.category_id == category.id).values(
            category=other.slug, category_id=other.id, severity=severity_sql(other.severity),
            category_locked=False,
        )
    )
    await db.execute(update(Source).where(Source.category_id == category.id).values(category_id=None))
    return result.rowcount or 0


async def apply_category_severity(db: AsyncSession, category: Category) -> int:
    """Kategoriya jiddiyligi o'zgarganda uning hodisalariga qo'llaydi (ulagich ko'targan daraja saqlanadi)."""
    result = await db.execute(
        update(EventRecord).where(EventRecord.category_id == category.id)
        .values(severity=severity_sql(category.severity))
    )
    return result.rowcount or 0
