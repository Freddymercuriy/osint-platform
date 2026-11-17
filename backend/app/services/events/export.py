"""Hodisalar eksporti (CSV / JSON) — Events sahifasidagi filtrlar bilan.

CSV formula injection: hodisa matni tashqi manbadan (Telegram, RSS) keladi — `=`, `+`, `-`, `@` (va tab / CR) bilan
boshlangan katak Excel / LibreOffice'da formula sifatida bajarilishi mumkin. Bunday katak oldiga `'` qo'yiladi (OWASP).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from app.schemas import EventItemOut

MAX_ROWS = 5000  # bitta eksportdagi eng ko'p hodisa (eng yangilari)
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")

COLUMNS = (
    "id", "published", "first_seen", "scope", "category", "severity", "title", "summary", "url", "source",
    "channel", "countries", "sector", "actor", "matched_keywords", "also_reported_by", "lang", "display_lang",
    "original_title",
)


def safe_cell(value: Any) -> str:
    """CSV katagi: ro'yxat → `; ` bilan, sana → ISO, formula bo'lib qolishi mumkin bo'lgan matn → `'` bilan."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list | tuple):
        value = "; ".join(str(v) for v in value)
    s = str(value)
    return "'" + s if s.startswith(_FORMULA_START) else s


def _reported_by(item: EventItemOut) -> list[str]:
    return [str(r.get("source")) for r in item.also_reported_by if isinstance(r, dict) and r.get("source")]


def row_of(item: EventItemOut) -> dict[str, Any]:
    return {
        "id": item.id, "published": item.published, "first_seen": item.first_seen, "scope": item.scope,
        "category": item.category, "severity": item.severity, "title": item.title, "summary": item.summary,
        "url": item.url, "source": item.source, "channel": item.channel, "countries": item.countries,
        "sector": item.sector, "actor": item.actor, "matched_keywords": item.matched_keywords,
        "also_reported_by": _reported_by(item), "lang": item.source_lang or item.lang,
        "display_lang": item.display_lang,
        # tarjima ko'rsatilgan bo'lsa — asl sarlavha ham (aks holda takror bo'lmasin)
        "original_title": item.original_title if item.original_title != item.title else None,
    }


def to_csv(items: list[EventItemOut]) -> str:
    """UTF-8 BOM bilan (Excel kirill / o'zbek harflarini to'g'ri ochadi)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(COLUMNS)
    for it in items:
        row = row_of(it)
        w.writerow([safe_cell(row[c]) for c in COLUMNS])
    return "﻿" + buf.getvalue()


def to_json(items: list[EventItemOut], *, filters: dict[str, Any], total: int, exported_at: datetime) -> dict:
    rows = [row_of(it) for it in items]
    for r in rows:
        for k in ("published", "first_seen"):
            if isinstance(r[k], datetime):
                r[k] = r[k].isoformat()
    return {
        "exported_at": exported_at.isoformat(), "filters": filters, "total": total, "count": len(rows),
        "truncated": total > len(rows), "max_rows": MAX_ROWS, "items": rows,
    }
