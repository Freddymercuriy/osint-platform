"""Kuzatuv ro'yxati bilan moslash (sof funksiyalar).

- Butun so'z bilan (`filters._kw_regex(whole_word=True)`): "payme" → "payment" ga mos EMAS; apostroflar har xil
  yozilishi va yo'qligi ("o'zbek" ≈ "oʻzbek" ≈ "ozbek") — mavjud filtrlar bilan bir xil qoida.
- Lotin ↔ kirill: har nom / alias uchun o'zbekcha ikkinchi yozuvi avtomatik qo'shiladi (`uz_to_cyrillic` /
  `uz_to_latin`, latin.jaybi.uz dvigateli) — "Kapitalbank" ≈ "Капиталбанк".
- Qayerdan qidiriladi: sarlavha, matn, tarjimalar (en / ru / uz), `matched_keywords`, `extra.victim`, `extra.domain`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.services.events.filters import _kw_regex
from app.services.i18n.text import is_cyrillic, uz_to_cyrillic, uz_to_latin

MIN_TERM = 3  # bundan qisqa nom / alias e'tiborsiz (shovqin)


@dataclass
class CompiledWatch:
    id: int | None
    kind: str
    name: str
    country: str | None
    terms: list[str] = field(default_factory=list)
    patterns: list[re.Pattern[str]] = field(default_factory=list)


def terms_of(name: str, aliases: Iterable[str] | None) -> list[str]:
    out: list[str] = []
    for raw in [name, *(aliases or [])]:
        term = re.sub(r"\s+", " ", (raw or "").strip())
        if len(term) < MIN_TERM:
            continue
        variants = [term]
        try:
            variants.append(uz_to_latin(term) if is_cyrillic(term) else uz_to_cyrillic(term))
        except Exception:  # noqa: BLE001 — transliteratsiya xatosi moslashni to'xtatmasin
            pass
        for v in variants:
            v = v.strip()
            if len(v) >= MIN_TERM and v.lower() not in {x.lower() for x in out}:
                out.append(v)
    return out


def compile_entry(entry: Any) -> CompiledWatch:
    cw = CompiledWatch(id=getattr(entry, "id", None), kind=entry.kind, name=entry.name,
                       country=getattr(entry, "country", None))
    cw.terms = terms_of(entry.name, getattr(entry, "aliases", None))
    cw.patterns = [_kw_regex(t, whole_word=True) for t in cw.terms]
    return cw


def compile_watchlist(entries: Iterable[Any]) -> list[CompiledWatch]:
    return [compile_entry(e) for e in entries if getattr(e, "enabled", True)]


def event_texts(title: str | None, summary: str | None, matched_keywords: Iterable[str] | None = None,
                extra: dict | None = None, translations: Iterable[tuple[str | None, str | None]] = ()) -> list[str]:
    ex = extra or {}
    texts = [title or "", summary or "", " ; ".join(matched_keywords or [])]
    for key in ("victim", "domain"):
        if ex.get(key):
            texts.append(str(ex[key]))
    for t, s in translations:
        texts += [t or "", s or ""]
    return [re.sub(r"\s+", " ", x) for x in texts if x and x.strip()]


def match(compiled: list[CompiledWatch], texts: list[str]) -> list[CompiledWatch]:
    """Matnlarda uchragan yozuvlar (tartib: kuzatuv ro'yxati tartibida)."""
    blob = "\n".join(texts)
    if not blob:
        return []
    return [cw for cw in compiled if any(p.search(blob) for p in cw.patterns)]
