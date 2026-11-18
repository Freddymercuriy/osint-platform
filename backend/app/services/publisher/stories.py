"""Bitta voqea — kanalda bitta post: boshqa nashr yozgan xuddi shu voqea qayta chiqmaydi.

Yig'ishda (`events/dedup.py`) hodisalar faqat original sarlavhalar bo'yicha birlashadi — bir voqeani turli tilda va
turlicha yozgan nashrlar (masalan, bitta ekstraditsiya haqida 5 ta inglizcha maqola, UzDaily'ning ruscha va inglizcha
xabari) alohida hodisa bo'lib qoladi. Kanal har postni o'z tilida (tarjima) chiqaradi, shuning uchun bu yerda
solishtirish shu tildagi matn bo'yicha — bir tilga keltirilgan sarlavhalarda umumiy nomlar ko'rinadi.

- Matn → belgilar: so'z o'zagi (birinchi 5 harf, 4 harfdan qisqa va bog'lovchilar tashlanadi), o'nli son ("2,1",
  "278,3" — juda aniq dalil), 3+ xonali son.
- Og'irlik — IDF: oxirgi 14 kundagi shu tildagi tarjimalar korpusi (soatiga yangilanadi).
- t — sarlavhalar kosinus o'xshashligi, f — sarlavha + matn boshi (400 belgi).
- Noyob nom — ikkala sarlavhada bor, korpusning ≤1 % hujjatida uchraydigan va umumiy so'z bo'lmagan belgi
  (Rezet, Kaspersky, Italiya, "278,3"). Umumiy so'zlar (`GENERIC`: fosh, mlrd, hujum, prokuratura ...) kiber-korpusda
  ham kam uchraydi, lekin voqeani ajratmaydi — jonli bazada noto'g'ri birlashishlar shulardan edi.

Bitta voqea, agar veto bo'lmasa va:
  A: t ≥ 0.5 va f ≥ 0.2;
  B: ≥ 1 noyob nom, max(t, f) ≥ 0.3 va min(t, f) ≥ 0.15;
  C: ≥ 2 noyob nom va max(t, f) ≥ 0.25.
Veto: vaqt farqi 48 soatdan ko'p; ikkalasida davlat bor, lekin umumiysi yo'q; sarlavhada 3 tadan kam belgi;
bir manba bir tilda (UZCERT'ning turli e'lonlari) — faqat deyarli bir xil matn (t va f ≥ 0.8) takror.
Kalibrlash: jonli bazadagi 1665 hodisa (2026-11-18) — 120 mintaqaviy hodisadagi barcha ma'lum takror guruhlari
ushlandi, noto'g'ri birlashish yo'q; global oqimda ham juftlarning aksariyati haqiqiy takror.
"""

from __future__ import annotations

import math
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventRecord, EventTranslation
from app.services.i18n.text import is_cyrillic, uz_to_latin

WINDOW = timedelta(hours=48)
CORPUS_DAYS = timedelta(days=14)
CORPUS_LIMIT = 6000
CORPUS_TTL = 3600.0  # sekund
SUMMARY_CHARS = 400
RARE_SHARE = 0.01

T_STRONG, F_MIN = 0.5, 0.2  # A
ONE_MAX, ONE_MIN = 0.3, 0.15  # B
TWO_MAX = 0.25  # C
SAME_SOURCE = 0.8

_APOS = re.compile("['‘’ʻʼ`]")
_WORD = re.compile(r"\d+(?:[.,]\d+)?|[^\W\d_]+")
_STOP = frozenset("bilan uchun orqali mumkin haqida boyicha".split())
GENERIC = frozenset("""
fosh olind hibsg ushla qolga mlrd milli oyda yilda bizne aldas aldag firib jinoy guruh kiber xaker hujum malum proku
shubh toshk tuman viloy shaha kriti zaifl aniql hali ostid ostig aybla masla jarim tosiq kunga mudda oxirg nuqta xush
kelib namoy mahsu samol yangi dastu tizim kompa foyda
""".split())


def tokens(text: str, lang: str = "uz") -> list[str]:
    if lang == "uz" and is_cyrillic(text):
        text = uz_to_latin(text)
    out: list[str] = []
    for m in _WORD.finditer(_APOS.sub("", (text or "").lower().replace("ё", "е"))):
        w = m.group()
        if w[0].isdigit():
            if "," in w or "." in w:
                out.append(w.replace(",", "."))
            elif len(w) >= 3:
                out.append(w)
        elif len(w) >= 4 and w not in _STOP:
            out.append(w[:5])
    return out


@dataclass
class Corpus:
    n: int
    df: Counter

    @property
    def rare_max(self) -> float:
        return max(3.0, RARE_SHARE * self.n)

    def idf(self, tok: str) -> float:
        return math.log((self.n + 1) / (self.df.get(tok, 0) + 1)) + 1

    def vector(self, toks: list[str]) -> dict[str, float]:
        return {t: (1 + math.log(c)) * self.idf(t) for t, c in Counter(toks).items()}


@dataclass
class Story:
    event_id: int
    source: str
    lang: str
    countries: frozenset[str]
    when: datetime
    title: frozenset[str]
    vt: dict[str, float]
    va: dict[str, float]
    post_id: int | None = None


def make(corpus: Corpus, ev: EventRecord, title: str, summary: str, text_lang: str,
         post_id: int | None = None) -> Story:
    """`title`/`summary` — kanal tilidagi matn (tarjima yoki, tarjima bo'lmasa, asl)."""
    tt = tokens(title, text_lang)
    ta = tt + tokens((summary or "")[:SUMMARY_CHARS], text_lang)
    return Story(event_id=ev.id, source=ev.source or "", lang=ev.lang or "", countries=frozenset(ev.countries or []),
                 when=ev.first_seen, title=frozenset(tt), vt=corpus.vector(tt), va=corpus.vector(ta), post_id=post_id)


def _cos(a: dict[str, float], b: dict[str, float]) -> float:
    num = sum(a[t] * b[t] for t in a.keys() & b.keys())
    den = math.sqrt(sum(v * v for v in a.values()) * sum(v * v for v in b.values()))
    return num / den if den else 0.0


def same_story(a: Story, b: Story, corpus: Corpus) -> bool:
    if abs(a.when - b.when) > WINDOW:
        return False
    if a.countries and b.countries and not (a.countries & b.countries):
        return False
    if len(a.title) < 3 or len(b.title) < 3:
        return False
    t, f = _cos(a.vt, b.vt), _cos(a.va, b.va)
    if a.source == b.source and a.lang == b.lang:
        return t >= SAME_SOURCE and f >= SAME_SOURCE
    if t >= T_STRONG and f >= F_MIN:
        return True
    names = [x for x in a.title & b.title if x not in GENERIC and corpus.df.get(x, 0) <= corpus.rare_max]
    hi, lo = max(t, f), min(t, f)
    return (bool(names) and hi >= ONE_MAX and lo >= ONE_MIN) or (len(names) >= 2 and hi >= TWO_MAX)


def find_duplicate(story: Story, posted: list[Story], corpus: Corpus) -> Story | None:
    return next((p for p in posted if p.event_id != story.event_id and same_story(story, p, corpus)), None)


_cache: dict[str, tuple[float, Corpus]] = {}


def clear_cache() -> None:
    _cache.clear()


async def corpus_for(db: AsyncSession, lang: str, now: datetime) -> Corpus:
    """Shu tildagi tarjimalar bo'yicha hujjat chastotalari (keshlanadi — `CORPUS_TTL`)."""
    hit = _cache.get(lang)
    if hit is not None and hit[0] > time.monotonic():
        return hit[1]
    rows = (await db.execute(
        select(EventTranslation.title, EventTranslation.summary)
        .join(EventRecord, EventRecord.id == EventTranslation.event_id)
        .where(EventTranslation.lang == lang, EventTranslation.status == "done",
               EventRecord.first_seen >= now - CORPUS_DAYS)
        .order_by(EventRecord.first_seen.desc())
        .limit(CORPUS_LIMIT)
    )).all()
    df: Counter = Counter()
    for title, summary in rows:
        df.update(set(tokens(f"{title or ''} {(summary or '')[:SUMMARY_CHARS]}", lang)))
    corpus = Corpus(n=len(rows), df=df)
    _cache[lang] = (time.monotonic() + CORPUS_TTL, corpus)
    return corpus
