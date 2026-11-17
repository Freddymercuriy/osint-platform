"""Sizish (leak) qoidalarini kengaytirish va shu o'zgarish ta'sir qilgan hodisalarni qayta tasniflash

Topilgan bo'shliqlar (Dark Web Intelligence, NewsNow, BleepingComputer va boshqalar — "other" da qolib, 🔔 bermagan):
- yolg'iz "breach" ot sifatida ("Amadeus breach", "third-party vendor breach") — faqat "breached", "data breach" bor edi;
- yozuvlar soni / hajm: "8.3M records", "40M-record", "2.8GB database";
- "stolen SharePoint data", "hackers stole payment card details" (eski pattern "stole " dan keyin bo'shliq kutardi);
- "customer / member / consumer database", "citizen data", "data dump", "data theft", "data exposure";
- "data ... offered on dark web", "database ... claimed on cybercrime forum".
Ransomware: "ransomware group ... stolen data" maqolasi leak'ka o'tib ketmasin — guruh iborasi pattern sifatida.

Qoidalar admin panelida tahrirlanadi — shuning uchun ustidan yozilmaydi, faqat yo'q bandlar qo'shiladi.
Hodisalar: faqat eski qoidalar saqlangan kategoriyani bergan va yangi qoidalar boshqasini beradigan (ya'ni aynan shu
o'zgarish ta'sir qilgan) hodisalar ko'chiriladi; qo'lda qo'yilgan, ulagich / manba bergan kategoriyalar tegilmaydi.
Oldingi kategoriya `extra.category_before_0017` da — downgrade uni qaytaradi.

Revision ID: 0017_leak_rules
Revises: 0016_telegram_global
Create Date: 2026-11-17
"""
import json
from collections.abc import Sequence
from types import SimpleNamespace

import sqlalchemy as sa
from alembic import op

revision: str = "0017_leak_rules"
down_revision: str | None = "0016_telegram_global"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MARK = "category_before_0017"
SEVERITIES = ("info", "low", "medium", "high", "critical")

LEAK_STEMS = {
    "en": ["breach ", "breaches ", "data theft", "data exposure", "data dump", "database dump", "customer data",
           "customer records", "customer database", "user database", "member database", "consumer database",
           "citizen data", "personal information", "stolen data", "exfiltrated data"],
}
LEAK_PATTERNS = [
    # "8.3M records", "40M-record", "11M Optus customer records", "1,2 млн записей" ("2025 records show" emas)
    r"(?<!\w)\d[\d.,]*\s?(?:k|m|mln|million|bn|billion|тыс\w*|млн|млрд)?\s?-?\s?(?:\w+\s){0,2}"
    r"(?:records?|rows|записей|записи)(?!\w)(?!\s+(?:show|indicate|reveal))",
    # "2.8GB database", "500 GB of data"
    r"(?<!\w)\d[\d.,]*\s?(?:gb|tb|гб|тб)(?!\w)\W+(?:\w+\W+){0,3}"
    r"(?:databases?|db|data|dumps?|archives?|files|records|баз\w*|данн\w*|архив\w*|файл\w*)",
    # "stolen SharePoint data", "hackers stole payment card details"
    r"(?:stole|stolen|exfiltrated|dumped)\W+(?:\w+\W+){0,3}(?:data|databases?|records|documents|files|information|details)",
    # "citizen data ... offered on dark web", "database ... claimed on cybercrime forum"
    r"(?:databases?|data|records|dumps?|баз\w*|данн\w*)\W+(?:\w+\W+){0,8}(?:dark ?web|darknet|даркнет|"
    r"cybercrime forum|hacking forum|hacker forum|breach ?forums|underground forum)",
]
RANSOMWARE_PATTERNS = [r"ransomware\W+(?:group|gang|operators?|operation|crew|actors?)(?!\w)"]

ADDITIONS = {
    "leak": {"stems": LEAK_STEMS, "patterns": LEAK_PATTERNS},
    "ransomware": {"stems": {}, "patterns": RANSOMWARE_PATTERNS},
}


def _merge(rules: dict | None, add: dict, *, remove: bool) -> dict:
    """Admin tahrirlarini saqlab qo'shadi (yoki aynan qo'shilgan bandlarni olib tashlaydi)."""
    out = json.loads(json.dumps(rules or {}))
    stems = out.setdefault("stems", {})
    for lang, words in add["stems"].items():
        cur = stems.get(lang) or []
        stems[lang] = [w for w in cur if w not in words] if remove else cur + [w for w in words if w not in cur]
    cur = out.get("patterns") or []
    out["patterns"] = ([p for p in cur if p not in add["patterns"]] if remove
                       else cur + [p for p in add["patterns"] if p not in cur])
    return out


def _categories(conn) -> list[SimpleNamespace]:
    return [SimpleNamespace(id=r.id, slug=r.slug, rules=r.rules or {}, severity=r.severity, sort_order=r.sort_order,
                            enabled=r.enabled)
            for r in conn.execute(sa.text(
                "select id, slug, rules, severity, sort_order, enabled from categories")).all()]


def _severity(category_severity: str, floor: str | None) -> str:
    rank = {s: i for i, s in enumerate(SEVERITIES)}
    return floor if floor and rank.get(floor, 0) > rank.get(category_severity, 0) else category_severity


def upgrade() -> None:
    from app.services.events.classifier import classify, compile_categories

    conn = op.get_bind()
    cats = _categories(conn)
    old = compile_categories(cats)
    for c in cats:
        if c.slug in ADDITIONS:
            c.rules = _merge(c.rules, ADDITIONS[c.slug], remove=False)
            conn.execute(sa.text("update categories set rules = cast(:r as jsonb) where id = :id"),
                         {"r": json.dumps(c.rules, ensure_ascii=False), "id": c.id})
    new = compile_categories(cats)
    by_slug = {c.slug: c for c in cats}

    fixed_sources = {r.id for r in conn.execute(sa.text("select id from sources where category_id is not null"))}
    rows = conn.execute(sa.text(
        "select id, title, summary, category, source_id, extra from events where not category_locked"
    )).all()
    for r in rows:
        extra = dict(r.extra or {})
        if extra.get("fixed_category") or (r.source_id in fixed_sources and not extra.get("category_free")):
            continue
        if classify(r.title, r.summary, old).slug != r.category:
            continue  # kategoriya boshqa yo'l bilan qo'yilgan (ulagich, eski qoidalar) — tegmaymiz
        c = classify(r.title, r.summary, new)
        target = by_slug.get(c.slug)
        if c.slug == r.category or target is None:
            continue
        extra[MARK] = r.category
        extra["classifier"] = {"score": c.score, "hits": c.hits}
        conn.execute(sa.text(
            "update events set category = :slug, category_id = :cid, severity = :sev, extra = cast(:extra as jsonb) "
            "where id = :id"
        ), dict(slug=target.slug, cid=target.id, sev=_severity(target.severity, extra.get("severity_floor")),
                extra=json.dumps(extra, ensure_ascii=False), id=r.id))


def downgrade() -> None:
    conn = op.get_bind()
    cats = _categories(conn)
    by_slug = {c.slug: c for c in cats}
    for c in cats:
        if c.slug in ADDITIONS:
            conn.execute(sa.text("update categories set rules = cast(:r as jsonb) where id = :id"), {
                "r": json.dumps(_merge(c.rules, ADDITIONS[c.slug], remove=True), ensure_ascii=False), "id": c.id})
    # keyin qo'lda o'zgartirilgan (category_locked) hodisa — admin qarori, qaytarilmaydi
    rows = conn.execute(sa.text(
        f"select id, extra from events where extra ? '{MARK}' and not category_locked"
    )).all()
    for r in rows:
        extra = dict(r.extra or {})
        prev = by_slug.get(extra.pop(MARK))
        if prev is None:
            prev = by_slug["other"]
        extra.pop("classifier", None)
        conn.execute(sa.text(
            "update events set category = :slug, category_id = :cid, severity = :sev, extra = cast(:extra as jsonb) "
            "where id = :id"
        ), dict(slug=prev.slug, cid=prev.id, sev=_severity(prev.severity, extra.get("severity_floor")),
                extra=json.dumps(extra, ensure_ascii=False), id=r.id))
