"""Hodisani mavzu kategoriyasiga ajratish (qoidalar — ma'lumot, `categories.rules`, admin tahrirlaydi).

Tartib: manbaning qat'iy kategoriyasi → ulagich aniq bilgan kategoriya → eng yuqori ballli qoida → `other`.

`rules` shakli:
    {
      "stems":    {"en": [...], "ru": [...], "uz": [...], "kk": [...]},   # so'z boshlanishlari (chap chegara bilan)
      "patterns": [regex, ...],                                         # kontekstli iboralar
      "exclude":  [regex, ...],                                         # mos kelsa — bu kategoriya 0 ball
      "weight":   1.0,                                                  # umumiy kategoriyalar uchun < 1
      "min_score": 1
    }
Stem oxirida bo'sh joy bo'lsa ("суд ") — butun so'z. Ball: sarlavhadagi stem 2, matndagi 1, pattern 3; × weight.
Teng ballda — jiddiyroq kategoriya, keyin `sort_order`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.models.category import SEVERITY_RANK
from app.services.events.feeds import TOPIC_NOISE

_APOS_RE = re.compile("['‘’ʻʼ`]")
_APOS_OPT = "'?"
_NOISE = [re.compile(n.replace("'", _APOS_OPT), re.IGNORECASE) for n in TOPIC_NOISE]
FALLBACK = "other"


# UZCERT kabi ba'zi manbalar o'zbek lotinini turkcha harflar bilan yozadi ("foş etildi", "qölga olindi")
_TR_UZ = str.maketrans({"ş": "sh", "ç": "ch", "ğ": "g'", "ö": "o'", "ı": "i"})


def normalize(text: str | None) -> str:
    text = _APOS_RE.sub("'", (text or "").lower().replace("ё", "е").translate(_TR_UZ))
    text = re.sub(r"\s+", " ", text).strip()
    for n in _NOISE:
        text = n.sub(" ", text)
    return text


def _stem_regex(stem: str) -> re.Pattern[str] | None:
    whole = stem.endswith(" ")
    stem = normalize(stem)
    if not stem:
        return None
    body = re.escape(stem).replace("'", _APOS_OPT)
    left = r"(?<!\w)" if stem[0].isalnum() else ""
    return re.compile(left + body + (r"(?!\w)" if whole else ""))


@dataclass
class CompiledCategory:
    slug: str
    severity: str
    sort_order: int
    weight: float
    min_score: float
    stems: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)
    patterns: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)
    exclude: list[re.Pattern[str]] = field(default_factory=list)


@dataclass
class Classification:
    slug: str
    score: float
    hits: list[str]


class RuleError(ValueError):
    pass


def validate_rules(rules: dict[str, Any]) -> dict[str, Any]:
    """Admin kiritgan qoidalarni tekshiradi (regexlar kompilyatsiya bo'lishi kerak). Normallashtirilgan nusxa."""
    if not isinstance(rules, dict):
        raise RuleError("rules — obyekt bo'lishi kerak")
    out: dict[str, Any] = {}
    stems = rules.get("stems") or {}
    if not isinstance(stems, dict):
        raise RuleError("rules.stems — {til: [so'zlar]} ko'rinishida bo'lishi kerak")
    out["stems"] = {}
    for lang, words in stems.items():
        if not isinstance(words, list) or not all(isinstance(w, str) for w in words):
            raise RuleError(f"rules.stems.{lang} — satrlar ro'yxati bo'lishi kerak")
        clean = [w for w in (x.strip(" \t\n").lower() + (" " if x.endswith(" ") else "") for x in words) if w.strip()]
        if len(clean) > 300:
            raise RuleError(f"rules.stems.{lang} — juda ko'p (≤ 300)")
        out["stems"][str(lang)[:8]] = clean
    for key in ("patterns", "exclude"):
        items = rules.get(key) or []
        if not isinstance(items, list) or not all(isinstance(p, str) for p in items):
            raise RuleError(f"rules.{key} — regex satrlar ro'yxati bo'lishi kerak")
        for p in items:
            if len(p) > 500:
                raise RuleError(f"rules.{key}: regex juda uzun")
            try:
                re.compile(p)
            except re.error as exc:
                raise RuleError(f"rules.{key}: noto'g'ri regex {p!r}: {exc}") from exc
        out[key] = items
    for key, default, lo, hi in (("weight", 1.0, 0.0, 10.0), ("min_score", 1.0, 0.0, 100.0)):
        try:
            val = float(rules.get(key, default))
        except (TypeError, ValueError) as exc:
            raise RuleError(f"rules.{key} — son bo'lishi kerak") from exc
        if not lo <= val <= hi:
            raise RuleError(f"rules.{key} — {lo}..{hi} oralig'ida")
        out[key] = val
    return out


def compile_categories(categories: Iterable[Any]) -> list[CompiledCategory]:
    """`categories` — slug, rules, severity, sort_order, enabled atributli obyektlar (ORM yoki oddiy)."""
    out: list[CompiledCategory] = []
    for c in categories:
        if not getattr(c, "enabled", True) or c.slug == FALLBACK:
            continue
        rules = c.rules or {}
        cc = CompiledCategory(
            slug=c.slug, severity=c.severity, sort_order=c.sort_order,
            weight=float(rules.get("weight", 1.0)), min_score=float(rules.get("min_score", 1.0)),
        )
        for words in (rules.get("stems") or {}).values():
            for w in words:
                rx = _stem_regex(w)
                if rx is not None:
                    cc.stems.append((w.strip(), rx))
        for p in rules.get("patterns") or []:
            try:
                cc.patterns.append((p, re.compile(p, re.IGNORECASE)))
            except re.error:
                continue  # admin API tekshiradi; bu yerda xato qoidani tashlab ketamiz
        for p in rules.get("exclude") or []:
            try:
                cc.exclude.append(re.compile(p, re.IGNORECASE))
            except re.error:
                continue
        if cc.stems or cc.patterns:
            out.append(cc)
    return out


def classify(title: str | None, summary: str | None, compiled: list[CompiledCategory]) -> Classification:
    t, s = normalize(title), normalize(summary)
    both = f"{t} \n {s}"
    best: Classification | None = None
    best_key: tuple = ()
    for cc in compiled:
        if any(x.search(both) for x in cc.exclude):
            continue
        score, hits = 0.0, []
        for word, rx in cc.stems:
            if rx.search(t):
                score += 2
                hits.append(word)
            elif rx.search(s):
                score += 1
                hits.append(word)
        for p, rx in cc.patterns:
            if rx.search(both):
                score += 3
                hits.append(f"/{p[:40]}/")
        score *= cc.weight
        if score <= 0 or score < cc.min_score:
            continue
        key = (score, SEVERITY_RANK.get(cc.severity, 0), -cc.sort_order)
        if best is None or key > best_key:
            best, best_key = Classification(cc.slug, round(score, 2), hits[:8]), key
    return best or Classification(FALLBACK, 0.0, [])
