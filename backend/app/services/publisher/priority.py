"""Hodisa ustuvorligi: ball (0–100), band va sabablar — bitta sof funksiya (`compute`).

Rejalashtiruvchi, Events sahifasi va simulyatsiya shu funksiyadan foydalanadi — natijalar doim bir xil.
Og'irliklar va band chegaralari — ma'lumot (`publisher_settings`, admin tahrirlaydi); bu yerdagi `DEFAULT_*` —
qator yo'q bo'lsa va yangi kalitlar uchun zaxira (migratsiya 0018 dagi qiymatlar bilan bir xil).

Sabab kodlari (frontend va post matni tarjima qiladi): sev_<severity>, country_uz, country_ca (arg: davlat),
sector (arg), watch_org / watch_product / watch_person (arg: nom), official_source, multi_source (arg: manbalar soni),
records_100k / records_1m (arg: son), stale (arg: soat), underground_only, global_cap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.publisher import BANDS, BAND_RANK

CA_OTHER = ("KZ", "KG", "TJ", "TM")

DEFAULT_WEIGHTS: dict[str, Any] = {
    "severity": {"critical": 50, "high": 35, "medium": 20, "low": 10, "info": 0},
    "country_uz": 30, "country_ca": 15,
    "sector": 10, "sectors": ["government", "finance", "telecom", "energy", "healthcare"],
    "watch_org": 40, "watch_product": 25, "watch_person": 30,
    "official": 10, "extra_source": 5, "extra_source_max": 2,
    "records_100k": 5, "records_1m": 10,
    "stale": -20, "stale_hours": 48,
    "underground_only": -10,
}
DEFAULT_BANDS: dict[str, int] = {"critical": 80, "high": 60, "medium": 40}

WATCH_GROUP = {"organisation": "watch_org", "domain": "watch_org", "brand": "watch_org",
               "product": "watch_product", "person": "watch_person"}


def merged_weights(stored: dict | None) -> dict[str, Any]:
    out = {**DEFAULT_WEIGHTS, **(stored or {})}
    out["severity"] = {**DEFAULT_WEIGHTS["severity"], **((stored or {}).get("severity") or {})}
    return out


def merged_bands(stored: dict | None) -> dict[str, int]:
    return {**DEFAULT_BANDS, **{k: int(v) for k, v in (stored or {}).items() if k in DEFAULT_BANDS}}


def band_of(score: int, bands: dict[str, int]) -> str:
    if score >= bands["critical"]:
        return "critical"
    if score >= bands["high"]:
        return "high"
    if score >= bands["medium"]:
        return "medium"
    return "low"


def band_at_least(band: str | None, minimum: str) -> bool:
    return BAND_RANK.get(band or "low", 0) >= BAND_RANK.get(minimum, 0)


# ---------------------------------------------------------------- manbalar va yozuvlar soni
_SOURCE_TAIL = re.compile(r"\s*\((?:google news|newsnow|google новости)\)\s*$", re.IGNORECASE)
_SOURCE_HEAD = re.compile(r"^\s*(?:google news|newsnow)\s*:\s*", re.IGNORECASE)


def source_key(name: str | None) -> str:
    """Manba identifikatori: "Cybernews (Google News)" va "Cybernews" — bitta manba (nusxa qayta sanalmaydi)."""
    s = _SOURCE_HEAD.sub("", _SOURCE_TAIL.sub("", (name or "").strip()))
    return re.sub(r"\s+", " ", s).lower()


def distinct_sources(primary: str | None, also_reported_by: list | None) -> list[str]:
    keys: list[str] = []
    for name in [primary, *[(r or {}).get("source") for r in (also_reported_by or []) if isinstance(r, dict)]]:
        k = source_key(name)
        if k and k not in keys:
            keys.append(k)
    return keys


_MULT = {"k": 1e3, "thousand": 1e3, "тыс": 1e3, "ming": 1e3,
         "m": 1e6, "mn": 1e6, "mln": 1e6, "million": 1e6, "millions": 1e6, "млн": 1e6, "million.": 1e6,
         "b": 1e9, "bn": 1e9, "billion": 1e9, "млрд": 1e9, "mlrd": 1e9}
_RECORDS_RE = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:[ ,.  ]\d{3})+|\d+(?:[.,]\d+)?)\+?\s*"
    r"(k|thousand|тыс\.?|ming|m|mn|mln|million|млн|b|bn|billion|млрд|mlrd)?(?!\w)\s*-?\s*"
    r"(?:[\w'’-]+\s+){0,2}?"
    r"(records?|accounts?|users?|customers?|clients?|members?|rows|entries|subscribers?|patients?|"
    r"записей|записи|аккаунтов|пользователей|клиентов|абонентов|"
    r"yozuv\w*|foydalanuvchi\w*|mijoz\w*|akkaunt\w*)(?!\w)",
    re.IGNORECASE,
)


def _parse_number(digits: str, mult: str | None) -> float | None:
    d = digits.replace(" ", " ").replace(" ", " ")
    if mult:
        # "8.3M", "1,2 млн" — kasr ajratgich
        try:
            base = float(d.replace(" ", "").replace(",", "."))
        except ValueError:
            return None
        return base * _MULT.get(mult.lower().rstrip("."), 1)
    # "44,080", "1 200 000", "10.000" — ming ajratgich
    if re.fullmatch(r"\d{1,3}(?:[ ,.]\d{3})+", d):
        return float(re.sub(r"[ ,.]", "", d))
    try:
        return float(d.replace(",", "."))
    except ValueError:
        return None


def record_count(title: str | None, summary: str | None, extra: dict | None) -> int | None:
    """Sizilgan yozuvlar soni: tuzilgan maydon (HIBP `pwn_count` ...) yoki matndan ("8.3M records")."""
    ex = extra or {}
    for k in ("pwn_count", "record_count", "records"):
        v = ex.get(k)
        if isinstance(v, int | float) and v > 0:
            return int(v)
    best: float = 0
    for m in _RECORDS_RE.finditer(f"{title or ''} \n {summary or ''}"):
        n = _parse_number(m.group(1), m.group(2))
        if n and n > best:
            best = n
    return int(best) if best >= 1 else None


# ---------------------------------------------------------------- hisoblash
@dataclass
class PriorityInput:
    severity: str
    countries: list[str]
    sector: str | None
    scope: str
    reliability: str | None  # asosiy manbaning ishonchliligi
    source: str | None
    also_reported_by: list = field(default_factory=list)
    published: datetime | None = None
    first_seen: datetime | None = None
    records: int | None = None
    watch_hits: list[tuple[str, str]] = field(default_factory=list)  # (kind, name)


@dataclass
class Priority:
    score: int
    band: str
    reasons: list[dict]

    def as_tuple(self) -> tuple:
        return self.score, self.band, self.reasons


def compute(inp: PriorityInput, weights: dict | None = None, bands: dict | None = None) -> Priority:
    w = merged_weights(weights)
    b = merged_bands(bands)
    reasons: list[dict] = []

    def add(code: str, points: int | float, arg: Any = None) -> None:
        p = int(round(points))
        if p == 0 and code not in ("global_cap",):
            return
        r: dict[str, Any] = {"code": code, "points": p}
        if arg not in (None, ""):
            r["arg"] = arg
        reasons.append(r)

    sev = inp.severity if inp.severity in w["severity"] else "info"
    add(f"sev_{sev}", w["severity"].get(sev, 0))

    countries = [c.upper() for c in (inp.countries or [])]
    if "UZ" in countries:
        add("country_uz", w["country_uz"])
    else:
        other = next((c for c in CA_OTHER if c in countries), None)
        if other:
            add("country_ca", w["country_ca"], other)

    if inp.sector and inp.sector in (w.get("sectors") or []):
        add("sector", w["sector"], inp.sector)

    seen_groups: set[str] = set()
    for kind, name in inp.watch_hits:
        group = WATCH_GROUP.get(kind)
        if group and group not in seen_groups:
            seen_groups.add(group)
            add(group, w[group], name)

    if inp.reliability == "official":
        add("official_source", w["official"])

    n_sources = len(distinct_sources(inp.source, inp.also_reported_by))
    extra = min(max(0, n_sources - 1), int(w["extra_source_max"]))
    if extra:
        add("multi_source", w["extra_source"] * extra, n_sources)

    if inp.records:
        if inp.records >= 1_000_000:
            add("records_1m", w["records_1m"], inp.records)
        elif inp.records >= 100_000:
            add("records_100k", w["records_100k"], inp.records)

    if inp.published and inp.first_seen:
        hours = (inp.first_seen - inp.published).total_seconds() / 3600
        if hours > float(w["stale_hours"]):
            add("stale", w["stale"], int(hours))

    if n_sources <= 1 and inp.reliability == "underground":
        add("underground_only", w["underground_only"])

    score = max(0, min(100, sum(r["points"] for r in reasons)))
    band = band_of(score, b)
    if inp.scope == "global" and not seen_groups and band != "low":
        # Kanal mintaqa haqida: kuzatuv ro'yxatiga tushmagan global hodisa qanchalik jiddiy bo'lmasin — past
        capped = max(0, b["medium"] - 1)
        add("global_cap", capped - score)
        score, band = capped, "low"
    return Priority(score=score, band=band, reasons=reasons)


__all__ = ["BANDS", "DEFAULT_BANDS", "DEFAULT_WEIGHTS", "Priority", "PriorityInput", "band_at_least", "band_of",
           "compute", "distinct_sources", "merged_bands", "merged_weights", "record_count", "source_key"]
