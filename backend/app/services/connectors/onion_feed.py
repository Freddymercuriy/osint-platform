"""Tor (.onion) saytlarining RSS / Atom lentalari — darknet forumlarining yangi mavzulari (MyBB
`syndication.php`, phpBB `feed.php`, XenForo `.rss` ...).

Qoidalar (docs/connectors.md, egasi qarori 2026-11-20):
- `.onion` faqat shu ulagich orqali, faqat admin qo'shgan manbalar (ro'yxat — `sources` jadvali), faqat Tor orqali
  (`ctx.tor`, TOR_PROXY_URL) va faqat v3 manzillar; lentalar va mavzu havolalari bitta .onion xostda.
- Faqat metadata: mavzu sarlavhasi, havolasi, vaqti, bo'lim nomi, muallif taxallusi (aktor). Post matni
  (description / content — sizgan ma'lumot namunasi, parol, shaxsiy ma'lumot bo'lishi mumkin), fayllar, rasmlar
  va mavzu sahifalari OLINMAYDI va saqlanmaydi.
- Login, CAPTCHA, challenge — chetlab o'tilmaydi: lenta o'rniga HTML sahifa qaytsa `SourceBlocked`.

Bloklanmaslik qoidalari (xushmuomalalik — niqoblanish EMAS; forum bizni bot deb to'smasligi uchun):
  1. Kam so'rov: har lenta o'z hajmiga mos tezlikda (`every_minutes` — sizishlar har yig'ishda, sekin bo'limlar
     soatlab bir marta), sahifa kichik (`limit=` 10–30, butun arxiv emas).
  2. Kunlik qat'iy limit (`max_requests_per_day`, default 80; UTC kuni): admin interval / "Hozir yig'ish" ni
     ko'p bossa ham forumga undan ortiq so'rov ketmaydi — qolgan lentalar keyingi kunga.
  3. Bir vaqtda bitta so'rov, orasida 10–30 s pauza (`http.ONION_PAUSE_RANGE`; xost navbati).
  4. "Sinash" (dry-run) — faqat birinchi lenta.
  5. 403 / 429 / challenge / login sahifasi — darhol to'xtaydi (qolgan lentalar so'ralmaydi), manba blocked /
     degraded, scheduler kutishni o'zi uzaytiradi (≤ 6 soat, Retry-After hurmat qilinadi).
  6. Faqat lenta: mavzu sahifalari, rasmlar, fayllar ochilmaydi (sayt yuklamasi — 1 so'rov / lenta).
  7. Niqob yo'q: User-Agent ochiq (platforma nomi), Tor zanjiri ataylab almashtirilmaydi, CAPTCHA yechilmaydi,
     login / akkaunt yo'q. Cookie (mehmon sessiyasi) mijozda saqlanadi — har so'rov yangi sessiya ochmaydi.

config:
  feeds — 1..10 ta: [{"url": "http://<v3>.onion/syndication.php?fid=10&limit=30",
                      "category": "leak" | null (null — klassifikator), "section": "Databases",
                      "every_minutes": 120 (0 / yo'q — har yig'ishda)}]
  site  — ko'rsatiladigan forum nomi ("DarkForums"); bo'sh — manba nomi
  repost_memory — bir xil sarlavha bilan qayta e'lon qilingan mavzularni eslab qolish soni (default 500)
  max_requests_per_day — kunlik so'rov limiti (1..500, default 80)

state: `seen` (sarlavha xeshlari), `fetched_at` {lenta url: oxirgi muvaffaqiyatli so'rov, ISO},
`budget` {"day": "YYYY-MM-DD", "count": N}.

Spam: forumlarda bir xil reklama mavzusi har kuni qayta ochiladi (sarlavha bir xil, havola boshqa) — normallashgan
sarlavha xeshi `state.seen` da saqlanadi va takrori olinmaydi.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import re
from calendar import timegm
from datetime import UTC, datetime, timedelta
from urllib.parse import urldefrag, urlsplit

import feedparser

from app.services.connectors.base import (
    ConfigError,
    Connector,
    ConnectorError,
    FetchContext,
    FetchResult,
    RawItem,
    SourceBlocked,
    SourceView,
    register,
)
from app.services.connectors.http import is_onion_url

MAX_FEEDS = 10
MAX_ITEMS_PER_FEED = 100
DEFAULT_MEMORY = 500
DEFAULT_DAILY_REQUESTS = 80
# Manba intervali jitter bilan (±20%) keladi — lenta `every_minutes` ning 75% o'tgan bo'lsa "navbatda" hisoblanadi
DUE_TOLERANCE = 0.75


def _now() -> datetime:  # testlar almashtiradi
    return datetime.now(UTC)
_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
_TAGS = re.compile(r"<[^>]+>")
_NORM = re.compile(r"[\W_]+", re.UNICODE)


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _plain(text: str | None, limit: int) -> str:
    """HTML teglarsiz, entity'lar ochilgan, bo'shliqlari yig'ilgan satr."""
    text = html.unescape(_TAGS.sub(" ", text or ""))
    return " ".join(text.split())[:limit]


def title_key(title: str) -> str:
    """Qayta e'lonlarni tanish uchun: kichik harf, faqat harf / raqam (emoji, tinish belgisi farq qilmaydi)."""
    norm = _NORM.sub(" ", title.lower()).strip()
    return hashlib.sha1(norm.encode()).hexdigest()[:16]


def _published(e) -> datetime | None:
    tm = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
    return datetime.fromtimestamp(timegm(tm), tz=UTC) if tm else None


def parse_feed(content: bytes, feed: dict, site: str, host: str) -> list[RawItem]:
    parsed = feedparser.parse(content)
    section = str(feed.get("section") or "").strip()
    category = feed.get("category") or None
    items: list[RawItem] = []
    for e in parsed.entries[:MAX_ITEMS_PER_FEED]:
        title = _plain(getattr(e, "title", ""), 300)
        link = urldefrag(str(getattr(e, "link", "") or "").strip())[0]
        if not title or not is_onion_url(link) or _host(link) != host:
            continue  # boshqa xostga / oddiy saytga havola — olinmaydi
        author = _plain(getattr(e, "author", ""), 64) or None
        extra = {"forum": site, "section": section, "author": author, "title_key": title_key(title)}
        items.append(RawItem(
            title=title, url=link,
            summary=f"{site} · {section}" if section else site,  # post matni EMAS (sizgan ma'lumot namunasi bo'lishi mumkin)
            published=_published(e), category=category, channel="forum", actor=author,
            extra={k: v for k, v in extra.items() if v},
        ))
    return items


@register
class OnionFeedConnector(Connector):
    kind = "onion_feed"
    title = "Tor (.onion) RSS lentasi — darknet forum mavzulari"
    config_fields = ("feeds", "site", "repost_memory")
    uses_tor = True
    slow_ms = 180_000  # 5 ta lenta Tor orqali: har biri 2–25 s

    def validate_config(self, config: dict) -> None:
        config = config or {}
        feeds = config.get("feeds")
        if not isinstance(feeds, list) or not 1 <= len(feeds) <= MAX_FEEDS:
            raise ConfigError(f"config.feeds — 1..{MAX_FEEDS} ta lenta ro'yxati bo'lishi kerak")
        hosts = set()
        for i, feed in enumerate(feeds):
            if not isinstance(feed, dict):
                raise ConfigError(f"config.feeds[{i}] — obyekt bo'lishi kerak")
            url = str(feed.get("url") or "")
            if not is_onion_url(url):
                raise ConfigError(f"config.feeds[{i}].url — faqat http(s)://<v3-manzil>.onion (Tor) bo'lishi mumkin")
            hosts.add(_host(url))
            cat = feed.get("category")
            if cat is not None and not (isinstance(cat, str) and _SLUG.fullmatch(cat)):
                raise ConfigError(f"config.feeds[{i}].category — kategoriya slug'i yoki null")
            sec = feed.get("section")
            if sec is not None and not (isinstance(sec, str) and len(sec) <= 64):
                raise ConfigError(f"config.feeds[{i}].section — ≤ 64 belgili satr")
            every = feed.get("every_minutes")
            if every is not None and not (isinstance(every, int) and not isinstance(every, bool) and 0 <= every <= 10080):
                raise ConfigError(f"config.feeds[{i}].every_minutes — 0..10080 (daqiqa)")
        if len(hosts) != 1:
            raise ConfigError("config.feeds — hamma lentalar bitta .onion saytdan bo'lishi kerak")
        site = config.get("site")
        if site is not None and not (isinstance(site, str) and len(site) <= 64):
            raise ConfigError("config.site — ≤ 64 belgili satr")
        mem = config.get("repost_memory", DEFAULT_MEMORY)
        if not isinstance(mem, int) or isinstance(mem, bool) or not 0 <= mem <= 5000:
            raise ConfigError("config.repost_memory — 0..5000")
        cap = config.get("max_requests_per_day", DEFAULT_DAILY_REQUESTS)
        if not isinstance(cap, int) or isinstance(cap, bool) or not 1 <= cap <= 500:
            raise ConfigError("config.max_requests_per_day — 1..500")

    def target_urls(self, source: SourceView) -> list[str]:
        # .onion DNS'da yo'q — SSRF (ommaviy IP) tekshiruvi qo'llanmaydi; xost validate_config'da (faqat v3 .onion)
        # va har so'rovda Tor mijozida tekshiriladi
        return []

    @staticmethod
    def _due(feed: dict, fetched_at: dict, now: datetime) -> bool:
        every = int(feed.get("every_minutes") or 0)
        last = fetched_at.get(feed["url"])
        if not every or not last:
            return True
        try:
            prev = datetime.fromisoformat(last)
        except (TypeError, ValueError):
            return True
        return now - prev >= timedelta(minutes=every * DUE_TOLERANCE)

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        cfg = ctx.source.config
        self.validate_config(cfg)
        if ctx.tor is None:  # scheduler buni oldinroq AuthMissing qiladi; bu — himoya
            raise ConnectorError("Tor mijozi berilmagan")
        site = str(cfg.get("site") or ctx.source.name)[:64]
        memory = int(cfg.get("repost_memory", DEFAULT_MEMORY))
        cap = int(cfg.get("max_requests_per_day", DEFAULT_DAILY_REQUESTS))
        prev_state = dict(ctx.source.state or {})
        now = _now()
        today = now.date().isoformat()

        if ctx.dry_run:
            # "Sinash": faqat birinchi lenta; holat (xotira, jadval, limit) ishlatilmaydi va saqlanmaydi
            plan, known, seen_before, fetched_at, used = [cfg["feeds"][0]], set(), [], {}, 0
        else:
            seen_before = list(prev_state.get("seen") or [])
            known = set(seen_before)
            fetched_at = dict(prev_state.get("fetched_at") or {})
            budget = prev_state.get("budget") or {}
            used = int(budget.get("count") or 0) if budget.get("day") == today else 0
            plan = [f for f in cfg["feeds"] if self._due(f, fetched_at, now)]

        items: list[RawItem] = []
        status: int | None = None
        failures: list[ConnectorError] = []
        done = 0
        capped = False
        for feed in plan:
            if not ctx.dry_run and used >= cap:
                capped = True  # kunlik limit — qolgan lentalar ertaga (xato emas)
                break
            url = feed["url"]
            used += 1
            try:
                resp = await ctx.tor.get(url, headers={"Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.5"})
            except SourceBlocked:
                raise  # 403 / 429 / challenge — qolgan lentalarni ham so'rab o'tirmaymiz
            except ConnectorError as exc:  # bitta lenta (vaqt tugadi) — qolganlari baribir yig'iladi
                failures.append(exc)
                continue
            status = resp.status_code
            ctype = resp.headers.get("content-type", "").lower()
            got = await asyncio.to_thread(parse_feed, resp.content, feed, site, _host(url))
            if not got and "html" in ctype:
                raise SourceBlocked("Lenta o'rniga HTML sahifa qaytdi (login / challenge?) — chetlab o'tilmaydi",
                                    http_status=status)
            items.extend(got)
            fetched_at[url] = now.isoformat()
            done += 1
        if failures and done == 0:
            raise failures[0]

        fresh: list[RawItem] = []
        batch: set[str] = set()
        for it in items:
            key = it.extra["title_key"]
            if key in known or key in batch:
                continue  # qayta e'lon qilingan reklama / bir xil mavzu
            batch.add(key)
            fresh.append(it)
        total = len(cfg["feeds"])
        note = f"lentalar: {done}/{total}"
        if len(plan) < total:
            note += " (qolganlari hali navbatda emas)"
        if capped:
            note += f"; kunlik so'rov limiti ({cap}) tugadi — qolgan lentalar ertaga"
        if failures:
            note += f"; {len(failures)} ta lenta xato: {failures[0]}"[:300]
        if ctx.dry_run:
            return FetchResult(fresh, status, note=note)
        new_keys = list(dict.fromkeys(it.extra["title_key"] for it in fresh))
        seen = (new_keys + seen_before)[:memory] if memory else []
        known_urls = {f["url"] for f in cfg["feeds"]}
        state = {**prev_state, "seen": seen, "budget": {"day": today, "count": used},
                 "fetched_at": {u: t for u, t in fetched_at.items() if u in known_urls}}
        return FetchResult(fresh, status, state=state, note=note)
