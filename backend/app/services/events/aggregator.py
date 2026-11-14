from __future__ import annotations

import asyncio
import html
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from calendar import timegm  # feedparser struct_time'lari UTC'da — mktime (lokal vaqt) emas

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.services.events.feeds import (
    FOREIGN_MARKERS,
    REGION_KEYWORDS,
    TOPIC_NOISE,
    TOPIC_PATTERNS,
    TOPIC_STEMS,
    UZ_KEYWORDS,  # noqa: F401  (orqaga moslik: REGION_KEYWORDS ning alias'i)
    Feed,
    enabled_feeds,
)

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class EventItem:
    source: str
    title: str
    url: str
    summary: str
    published: datetime | None
    lang: str
    category: str
    matched_keywords: list[str] = field(default_factory=list)
    channel: str = "news"  # news | telegram_channel | telegram_group | api


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


def _strip_own(text: str, feed: Feed) -> str:
    """Manbaning o'z domenini matndan olib tashlaydi ("... xabar beradi Tengrinews.kz" —
    bu `.kz` mintaqa belgisi emas, shunchaki manba imzosi)."""
    if feed.kind != "rss":
        return text
    host = re.sub(r"^https?://(?:www\.)?([^/]+).*$", r"\1", feed.url or "")
    if "." not in host:
        return text
    parts = host.split(".")
    for h in {host, ".".join(parts[-2:])}:  # "kz.kursiv.media" va "kursiv.media"
        text = re.sub(re.escape(h), " ", text, flags=re.IGNORECASE)
    return text


def _apply_filters(items: list[EventItem], feed: Feed) -> list[EventItem]:
    """Feed bayroqlari bo'yicha filtr (title + summary). Mos kelgan kalit so'zlar `matched_keywords` ga yoziladi."""
    out: list[EventItem] = []
    for i in items:
        text = f"{i.title} {i.summary}"
        hits: list[str] = []
        if feed.cyber_filter:
            h = _topic_hits(text)
            if not h:
                continue
            # Mahalliy sayt qayta bosgan jahon yangiligi: chet el belgisi bor, mintaqa so'zi yo'q
            if not feed.region_filter and _is_foreign(text) and not _is_region(_strip_own(text, feed)):
                continue
            hits += h
        if feed.region_filter:
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


# ---------------------------------------------------------------- manba turlari
async def _fetch_rss(client: httpx.AsyncClient, feed: Feed) -> list[EventItem]:
    resp = await client.get(feed.url)
    resp.raise_for_status()
    parsed = await asyncio.to_thread(feedparser.parse, resp.content)
    items: list[EventItem] = []
    for e in parsed.entries:
        link, title = getattr(e, "link", ""), _unescape(getattr(e, "title", "")).strip()
        if not link or not title:
            continue
        tm = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
        published = datetime.fromtimestamp(timegm(tm), tz=UTC) if tm else None
        items.append(EventItem(feed.name, title, link, _clean(getattr(e, "summary", "")),
                               published, feed.lang, feed.category))
    return items


# Google News nashri: til → (hl, gl, ceid)
_GNEWS_EDITION = {"ru": ("ru", "KZ", "KZ:ru"), "en": ("en-US", "US", "US:en")}
GOOGLE_NEWS_TAG = "(Google News)"


async def _fetch_google_news(client: httpx.AsyncClient, feed: Feed) -> list[EventItem]:
    """Google News RSS qidiruvi (feed.url — so'rov). Faqat sarlavha, nashr nomi, sana va
    Google havolasi olinadi — asl saytga murojaat qilinmaydi."""
    hl, gl, ceid = _GNEWS_EDITION.get(feed.lang, _GNEWS_EDITION["en"])
    resp = await client.get(
        "https://news.google.com/rss/search",
        params={"q": feed.url, "hl": hl, "gl": gl, "ceid": ceid},
    )
    resp.raise_for_status()
    parsed = await asyncio.to_thread(feedparser.parse, resp.content)
    items: list[EventItem] = []
    for e in parsed.entries:
        link, title = getattr(e, "link", ""), _unescape(getattr(e, "title", "")).strip()
        if not link or not title:
            continue
        src = getattr(e, "source", None)
        outlet = _unescape((src.get("title") if src else "") or "").strip() or feed.name
        # Google sarlavha oxiriga " - Nashr" qo'shadi
        if title.endswith(f" - {outlet}"):
            title = title[: -len(outlet) - 3].rstrip()
        tm = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
        published = datetime.fromtimestamp(timegm(tm), tz=UTC) if tm else None
        # description — faqat sarlavhaning takrori, shuning uchun summary bo'sh
        items.append(EventItem(f"{outlet} {GOOGLE_NEWS_TAG}"[:128], title, link, "",
                               published, feed.lang, feed.category))
    return items


_CA_CODES = ("UZ", "KZ", "KG", "TJ", "TM")
_CA_DOMAINS = tuple(f".{c.lower()}" for c in _CA_CODES)


async def _fetch_ransomware_live(client: httpx.AsyncClient, feed: Feed) -> list[EventItem]:
    """Yangi qurbonlar: BITTA /v2/recentvictims so'rovi (oxirgi ~100 ta), davlat kodi
    bo'yicha filtrlanadi (rate limit ~1 so'rov/daqiqa). feed.url — vergul bilan kodlar."""
    codes = {c.strip().upper() for c in (feed.url or ",".join(_CA_CODES)).split(",") if c.strip()}
    domains = tuple(f".{c.lower()}" for c in codes)
    resp = await client.get("https://api.ransomware.live/v2/recentvictims")
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):  # rate-limit javobi ({"message": ...})
        raise RuntimeError(str(data))
    items: list[EventItem] = []
    for v in data:
        country = (v.get("country") or "").strip().upper()
        domain = (v.get("domain") or "").strip().lower().rstrip("/")
        # Davlat maydoni bo'sh bo'lsa — milliy domen bo'yicha (masalan example.kz)
        if country not in codes and not (not country and domain.endswith(domains)):
            continue
        if not country:
            country = domain.rsplit(".", 1)[-1].upper()
        victim = (v.get("victim") or v.get("post_title") or "Noma'lum").strip()
        group = v.get("group") or v.get("group_name") or "?"
        activity = v.get("activity") or ""
        if activity.lower() in ("not found", "unknown"):
            activity = ""
        title = f"[{group}] {victim} ({country})" + (f" — {activity}" if activity else "")
        link = v.get("url") or ""
        if not link.startswith("https://www.ransomware.live/") or ".onion" in link:
            # .onion havolalar berilmaydi — ochiq ransomware.live sahifasi
            link = f"https://www.ransomware.live/group/{str(group).lower()}"
        items.append(EventItem(
            source=feed.name,
            title=title,
            url=link,
            summary=_clean(v.get("description") or ""),
            published=_parse_iso(v.get("discovered") or v.get("attackdate")),
            lang=feed.lang,
            category=feed.category,
            channel="api",
        ))
    return items


async def _fetch_telegram(client: httpx.AsyncClient, feed: Feed) -> list[EventItem]:
    channel = feed.url.lstrip("@")
    resp = await client.get(f"https://t.me/s/{channel}")
    resp.raise_for_status()
    soup = await asyncio.to_thread(BeautifulSoup, resp.text, "html.parser")
    items: list[EventItem] = []
    for msg in soup.select("div.tgme_widget_message[data-post]"):
        text_el = msg.select_one("div.tgme_widget_message_text")
        if text_el is None:
            continue
        text = text_el.get_text(" ", strip=True)
        time_el = msg.select_one("a.tgme_widget_message_date time")
        first_line = text.split(". ")[0]
        items.append(EventItem(
            source=f"TG: {feed.name}",
            title=first_line[:140] + ("..." if len(first_line) > 140 else ""),
            url=f"https://t.me/{msg['data-post']}",
            summary=_clean(text),
            published=_parse_iso(time_el.get("datetime") if time_el else None),
            lang=feed.lang,
            category=feed.category,
            channel="telegram_channel",
        ))
    return items


async def _fetch_telegram_user(_client: httpx.AsyncClient, feed: Feed) -> list[EventItem]:
    """Foydalanuvchining o'z akkaunti orqali a'zo bo'lgan kanal/guruhlar."""
    from app.core.config import settings
    from app.services import telegram_user as tg

    if not tg.is_configured():
        return []
    messages = await tg.fetch_messages()
    extra = settings.tg_extra_keywords_list
    leak_chats = settings.tg_leak_chats_list

    def category_for(chat) -> str:
        if leak_chats and tg.chat_matches(chat, leak_chats):
            return "leak"
        return "tg_group" if chat.kind == "group" else "telegram"

    extra_patterns = [(k, _kw_regex(k, whole_word=True)) for k in extra]
    keywords = (_UZ_PATTERNS + extra_patterns) if settings.tg_uz_filter else extra_patterns

    items: list[EventItem] = []
    seen: set[str] = set()
    # Yangilari birinchi — takrorlarda eng yangisi qoladi
    for m in sorted(messages, key=lambda x: x.date or datetime.min.replace(tzinfo=UTC),
                    reverse=True):
        hits, snippet = _match_snippet(m.text, keywords)
        if keywords and not hits:
            continue
        fingerprint = re.sub(r"\W+", "", m.text.lower())[:200]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        first_line = m.text.strip().split("\n")[0]
        items.append(EventItem(
            source=f"TG: {m.chat.title}",
            title=first_line[:140] + ("..." if len(first_line) > 140 else ""),
            url=m.url,
            summary=snippet,
            published=m.date,
            lang=feed.lang,
            category=category_for(m.chat),
            matched_keywords=hits,
            channel="telegram_group" if m.chat.kind == "group" else "telegram_channel",
        ))
    return items


_MAX_PARALLEL = 16  # bir vaqtdagi so'rovlar soni (manbalarni ortiqcha yuklamaslik)

_FETCHERS = {
    "rss": _fetch_rss,
    "ransomware_live": _fetch_ransomware_live,
    "google_news": _fetch_google_news,
    "telegram": _fetch_telegram,
    "telegram_user": _fetch_telegram_user,
}

# ---------------------------------------------------------------- kesh
# feed.name -> (saqlangan vaqt, itemlar). Rate-limitli API'lar uchun muhim.
_cache: dict[str, tuple[float, list[EventItem]]] = {}


async def _fetch_cached(
    client: httpx.AsyncClient,
    feed: Feed,
    force: bool = False,
    sem: asyncio.Semaphore | None = None,
) -> list[EventItem]:
    now = time.monotonic()
    cached = _cache.get(feed.name)
    # ransomware.live kabi rate-limitli manbalar uchun ttl force'da ham hurmat qilinadi
    min_age = feed.ttl if not force else min(feed.ttl, 60)
    min_age = max(min_age, feed.min_interval)
    if cached and now - cached[0] < min_age:
        return cached[1]
    fetcher = _FETCHERS.get(feed.kind)
    if fetcher is None:
        return []
    try:
        if sem is not None:
            async with sem:
                items = await fetcher(client, feed)
        else:
            items = await fetcher(client, feed)
    except Exception:
        # Xato bo'lsa eski keshni qaytaramiz (bo'lsa), aks holda bo'sh
        return cached[1] if cached else []
    if feed.region_filter or feed.cyber_filter:
        items = _apply_filters(items, feed)
    _cache[feed.name] = (now, items)
    return items


async def collect_all(force: bool = True) -> list[EventItem]:
    """Barcha yoqilgan manbalardan hammasini yig'adi (fon yig'uvchi uchun)."""
    headers = {"User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=12.0, headers=headers, follow_redirects=True) as client:
        sem = asyncio.Semaphore(_MAX_PARALLEL)
        batches = await asyncio.gather(
            *(_fetch_cached(client, f, force=force, sem=sem) for f in enabled_feeds())
        )
    return [i for batch in batches for i in batch]


async def fetch_events(
    limit: int = 40, query: str | None = None, category: str | None = None
) -> list[EventItem]:
    feeds = enabled_feeds()
    headers = {"User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=12.0, headers=headers, follow_redirects=True) as client:
        sem = asyncio.Semaphore(_MAX_PARALLEL)
        batches = await asyncio.gather(*(_fetch_cached(client, f, sem=sem) for f in feeds))

    items = [i for batch in batches for i in batch]
    # Kategoriya natija darajasida (bitta manba bir nechta kategoriya berishi mumkin; kesh tufayli arzon)
    if category:
        items = [i for i in items if i.category == category]
    if query:
        q = query.lower()
        items = [i for i in items if q in i.title.lower() or q in i.summary.lower()]
    items.sort(key=lambda i: i.published or datetime.min.replace(tzinfo=UTC), reverse=True)
    return items[:limit]
