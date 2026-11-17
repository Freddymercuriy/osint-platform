"""Matndan Markaziy Osiyo davlatlarini aniqlash (ISO kodlar: UZ, KZ, KG, TJ, TM)."""

from __future__ import annotations

import re

from app.services.events.filters import _flat, _region_regex
from app.services.events.feeds import COUNTRY_KEYWORDS

COUNTRY_CODES = tuple(COUNTRY_KEYWORDS)

_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    code: [_region_regex(k) for k in kws] for code, kws in COUNTRY_KEYWORDS.items()
}


def detect_countries(*texts: str | None) -> list[str]:
    """Matnda tilga olingan davlatlar (tartib: COUNTRY_KEYWORDS bo'yicha, takrorsiz)."""
    flat = _flat(" ".join(t for t in texts if t))
    if not flat:
        return []
    return [code for code, pats in _PATTERNS.items() if any(p.search(flat) for p in pats)]


# Soha (sector) — sarlavha/matndagi so'z boshlanishlari bo'yicha (dedup._SECTORS bilan bir xil lug'at)
SECTOR_NAMES = {"GOV": "government", "BANK": "finance", "HEALTH": "healthcare", "TELECOM": "telecom",
                "EDU": "education"}


def detect_sector(*texts: str | None) -> str | None:
    from app.services.events.dedup import _SECTORS

    words = re.findall(r"\w+", " ".join(t for t in texts if t).lower().replace("ё", "е"))
    for code, prefixes in _SECTORS.items():
        if any(w.startswith(p) for w in words for p in prefixes):
            return SECTOR_NAMES[code]
    return None
