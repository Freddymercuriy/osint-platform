"""Ikki kalibrlash tuzatishi (Bosqich 1 jonli tekshiruvidan)

1. Ransomware qoidasi: "qilin" (Qilin guruhi) stem edi — o'zbekcha fe'llarning boshiga mos kelardi ("jalb
   qilinadi", "taqdim qilinmoqda"). Natija: "Kiberfiribgarlikka qarshi tezkor markaz ochiladi" (Kun.uz) —
   ransomware / critical, 🔔. Endi butun so'z: "qilin ". Faqat shu stem bilan tasniflangan, qulflanmagan, qat'iy
   kategoriyasiz hodisalar qayta tasniflanadi; oldingi kategoriya `extra.category_before_0019` da.
2. Kuzatuv ro'yxati: "Ichki ishlar vazirligi (IIV)" va "Davlat xavfsizlik xizmati (DXX)" (0018, TG_EXTRA_KEYWORDS
   dan) o'chirib qo'yiladi — ular yangiliklarda odatda hodisani XABAR QILUVCHI ("IIV ma'lum qildi"), jabrlanuvchi
   emas: jonli bazadagi 5 ta moslikning 5 tasi shunday edi (pora, tezkor markaz ochilishi ...). Admin qayta yoqa oladi.
Ta'sirlangan hodisalarning ustuvorligi tozalanadi — housekeeping qayta hisoblaydi.

Revision ID: 0019_qilin_word_watch_agencies
Revises: 0018_priority
Create Date: 2026-11-17
"""
import json
from collections.abc import Sequence
from types import SimpleNamespace

import sqlalchemy as sa
from alembic import op

revision: str = "0019_qilin_word_watch_agencies"
down_revision: str | None = "0018_priority"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MARK = "category_before_0019"
AGENCIES = ("Ichki ishlar vazirligi (IIV)", "Davlat xavfsizlik xizmati (DXX)")
AGENCY_NOTE = (" | 0019: o'chirildi — yangiliklarda odatda hodisani xabar qiluvchi (\"IIV ma'lum qildi\"), "
               "jabrlanuvchi emas; kerak bo'lsa yoqing.")
SEVERITIES = ("info", "low", "medium", "high", "critical")


def _swap_stem(conn, old: str, new: str) -> None:
    row = conn.execute(sa.text("select id, rules from categories where slug = 'ransomware'")).first()
    if row is None:
        return
    rules = dict(row.rules or {})
    stems = {lang: [new if w == old else w for w in words] for lang, words in (rules.get("stems") or {}).items()}
    rules["stems"] = stems
    conn.execute(sa.text("update categories set rules = cast(:r as jsonb) where id = :id"),
                 {"r": json.dumps(rules, ensure_ascii=False), "id": row.id})


def _severity(cat_sev: str, floor: str | None) -> str:
    rank = {s: i for i, s in enumerate(SEVERITIES)}
    return floor if floor and rank.get(floor, 0) > rank.get(cat_sev, 0) else cat_sev


def upgrade() -> None:
    from app.services.events.classifier import classify, compile_categories

    conn = op.get_bind()
    _swap_stem(conn, "qilin", "qilin ")
    cats = [SimpleNamespace(id=r.id, slug=r.slug, rules=r.rules or {}, severity=r.severity, sort_order=r.sort_order,
                            enabled=r.enabled)
            for r in conn.execute(sa.text("select id, slug, rules, severity, sort_order, enabled from categories"))]
    by_slug = {c.slug: c for c in cats}
    compiled = compile_categories(cats)
    rows = conn.execute(sa.text(
        "select id, title, summary, category, extra from events where not category_locked "
        "and not (extra ? 'fixed_category') and extra->'classifier'->'hits' ? 'qilin'"
    )).all()
    for r in rows:
        c = classify(r.title, r.summary, compiled)
        target = by_slug.get(c.slug)
        if target is None or c.slug == r.category:
            continue
        extra = dict(r.extra or {})
        extra[MARK] = r.category
        extra["classifier"] = {"score": c.score, "hits": c.hits}
        conn.execute(sa.text(
            "update events set category = :slug, category_id = :cid, severity = :sev, extra = cast(:extra as jsonb), "
            "priority = null where id = :id"
        ), dict(slug=target.slug, cid=target.id, sev=_severity(target.severity, extra.get("severity_floor")),
                extra=json.dumps(extra, ensure_ascii=False), id=r.id))

    conn.execute(sa.text(
        "update watchlist set enabled = false, notes = notes || :note "
        "where name = any(:names) and enabled and notes like 'TG_EXTRA_KEYWORDS dan (0018)%'"
    ), {"note": AGENCY_NOTE, "names": list(AGENCIES)})
    conn.execute(sa.text(
        "update events set priority = null where exists (select 1 from jsonb_array_elements(priority_reasons) r "
        "where r->>'arg' = any(:names))"
    ), {"names": list(AGENCIES)})


def downgrade() -> None:
    conn = op.get_bind()
    _swap_stem(conn, "qilin ", "qilin")
    cats = {r.slug: r for r in conn.execute(sa.text("select id, slug, severity from categories"))}
    rows = conn.execute(sa.text(
        f"select id, extra from events where extra ? '{MARK}' and not category_locked"
    )).all()
    for r in rows:
        extra = dict(r.extra or {})
        prev = cats.get(extra.pop(MARK)) or cats.get("other")
        extra.pop("classifier", None)
        conn.execute(sa.text(
            "update events set category = :slug, category_id = :cid, severity = :sev, extra = cast(:extra as jsonb), "
            "priority = null where id = :id"
        ), dict(slug=prev.slug, cid=prev.id, sev=_severity(prev.severity, extra.get("severity_floor")),
                extra=json.dumps(extra, ensure_ascii=False), id=r.id))
    conn.execute(sa.text(
        "update watchlist set enabled = true, notes = replace(notes, :note, '') where position(:note in notes) > 0"
    ), {"note": AGENCY_NOTE})
