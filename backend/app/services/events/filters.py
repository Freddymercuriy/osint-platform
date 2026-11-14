"""Matn yordamchilari va manba filtrlari (hudud / mavzu / chet el).

Kalit so'z va regexlar `feeds.py` da (kodda qoladi); manbalar ro'yxati — bazada (`sources`).
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from app.services.events.feeds import (
    FOREIGN_MARKERS,
    REGION_KEYWORDS,
    TOPIC_NOISE,
    TOPIC_PATTERNS,
    TOPIC_STEMS,
)

if TYPE_CHECKING:
    from app.services.connectors.base import RawItem


class FilterSource(Protocol):
    """Filtr uchun manba bayroqlari (`models.Source` yoki test uchun oddiy obyekt)."""

    kind: str
    config: dict
    region_filter: bool
    cyber_filter: bool


# ---------------------------------------------------------------- yordamchilar
def _unescape(text: str) -> str:
    """HTML belgilari (&nbsp; &amp; &quot; ...) → oddiy matn; ikki marta kodlanganini ham."""
    for _ in range(2):
        text = html.unescape(text or "")
    return text.replace("\xa0", " ")


def _clean(text: str, limit: int = 300) -> str:
    text = _unescape(re.sub(r"<[^>]+>", "", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


# Apostrof variantlari: ' ‘ ’ ʻ ʼ ` — va ularning yo'qligi ("o'zbek" ≈ "ozbek" ≈ "oʻzbek")
_APOS = "['\u2018\u2019\u02bb\u02bc`]?"


def _apos(pattern: str) -> str:
    return pattern.replace("'", _APOS)


def _kw_regex(keyword: str, whole_word: bool) -> re.Pattern[str]:
    """Kalit so'z uchun chegarali regex.

    - whole_word=False (o'zak): "uzbek" → "uzbekistan" ham mos, lekin "xuzbek" emas.
    - whole_word=True (nom): "payme" → "payment" ga mos EMAS.
    - ".uz" kabi belgidan boshlanganlar: "day.uz" mos, ".uzum" emas.
    - Apostrof har xil yozilishlarga (va yo'qligiga) mos: "o'zbek" ≈ "oʻzbek" ≈ "ozbek".
    """
    esc = _apos(re.escape(keyword))
    left = r"(?<!\w)" if keyword[0].isalnum() else ""
    domain_like = not keyword[0].isalnum()  # ".uz" — domen oxiri, davomi bo'lmasligi kerak
    right = r"(?!\w)" if (whole_word or domain_like or not keyword[-1].isalnum()) else ""
    return re.compile(left + esc + right, re.IGNORECASE)


def _region_regex(keyword: str) -> re.Pattern[str]:
    """Hudud kalit so'zi. Domenlar (.tm, .kg ...) faqat so'z/defis dan keyin: "5.kg" mos emas."""
    if keyword.startswith("."):
        return re.compile(r"(?<=[a-z\-])" + re.escape(keyword) + r"(?![\w\-])", re.IGNORECASE)
    return _kw_regex(keyword, whole_word=False)


_UZ_PATTERNS = [(k, _region_regex(k)) for k in REGION_KEYWORDS]
_REGION_PATTERNS = _UZ_PATTERNS

_TOPIC_NOISE = [re.compile(_apos(n), re.IGNORECASE) for n in TOPIC_NOISE]
_TOPIC_PATTERNS: list[tuple[str, re.Pattern[str]]] = (
    [(k, _kw_regex(k, whole_word=False)) for k in TOPIC_STEMS]
    + [(label, re.compile(_apos(rx), re.IGNORECASE)) for label, rx in TOPIC_PATTERNS]
)


_FOREIGN_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(_apos(m) for m in FOREIGN_MARKERS) + ")", re.IGNORECASE
)


def _is_foreign(text: str) -> bool:
    """Matnda chet el belgisi bor (AQSH, FQB, "global" ...)."""
    return bool(_FOREIGN_RE.search(_flat(text)))


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _region_hits(text: str) -> list[str]:
    flat = _flat(text)
    return [k for k, p in _REGION_PATTERNS if p.search(flat)]


def _topic_hits(text: str) -> list[str]:
    """Kiber/leak mavzu belgilari (takrorsiz, tartib saqlangan). Shovqin iboralari olib tashlanadi."""
    flat = _flat(text)
    for n in _TOPIC_NOISE:
        flat = n.sub(" ", flat)
    hits: list[str] = []
    for label, p in _TOPIC_PATTERNS:
        if label not in hits and p.search(flat):
            hits.append(label)
    return hits


def _is_region(text: str) -> bool:
    flat = _flat(text)
    return any(p.search(flat) for _, p in _REGION_PATTERNS)


_is_uz = _is_region  # orqaga moslik


def _is_cyber(text: str) -> bool:
    return bool(_topic_hits(text))


def _strip_own(text: str, source: FilterSource) -> str:
    """Manbaning o'z domenini matndan olib tashlaydi ("... xabar beradi Tengrinews.kz" —
    bu `.kz` mintaqa belgisi emas, shunchaki manba imzosi)."""
    if source.kind != "rss":
        return text
    host = re.sub(r"^https?://(?:www\.)?([^/]+).*$", r"\1", (source.config or {}).get("url") or "")
    if "." not in host:
        return text
    parts = host.split(".")
    for h in {host, ".".join(parts[-2:])}:  # "kz.kursiv.media" va "kursiv.media"
        text = re.sub(re.escape(h), " ", text, flags=re.IGNORECASE)
    return text


def apply_filters(items: list[RawItem], source: FilterSource) -> list[RawItem]:
    """Manba bayroqlari bo'yicha filtr (title + summary). Mos kelgan kalit so'zlar `matched_keywords` ga."""
    out: list[RawItem] = []
    for i in items:
        text = f"{i.title} {i.summary}"
        hits: list[str] = []
        if source.cyber_filter:
            h = _topic_hits(text)
            if not h:
                continue
            # Mahalliy sayt qayta bosgan jahon yangiligi: chet el belgisi bor, mintaqa so'zi yo'q
            if not source.region_filter and _is_foreign(text) and not _is_region(_strip_own(text, source)):
                continue
            hits += h
        if source.region_filter:
            h = _region_hits(text)
            if not h:
                continue
            hits += h
        if hits:
            i.matched_keywords = list(dict.fromkeys(i.matched_keywords + hits))
        out.append(i)
    return out


def _match_snippet(
    text: str, patterns: list[tuple[str, re.Pattern[str]]], width: int = 260
) -> tuple[list[str], str]:
    """Topilgan kalit so'zlar va birinchi topilgan joy atrofidagi matn parchasi."""
    flat = re.sub(r"\s+", " ", text).strip()
    found = [(k, m.start()) for k, p in patterns if (m := p.search(flat))]
    if not found:
        return [], _clean(flat)
    hits = [k for k, _ in found]
    pos = min(s for _, s in found)
    start = max(0, pos - width // 3)
    end = min(len(flat), start + width)
    snippet = ("..." if start else "") + flat[start:end] + ("..." if end < len(flat) else "")
    return hits, snippet
