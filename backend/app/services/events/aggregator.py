from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from time import mktime

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.services.events.feeds import UZ_KEYWORDS, Feed, enabled_feeds

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


# ---------------------------------------------------------------- yordamchilar
def _clean(text: str, limit: int = 300) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
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


def _kw_regex(keyword: str, whole_word: bool) -> re.Pattern[str]:
    """Kalit so'z uchun chegarali regex.

    - whole_word=False (o'zak): "uzbek" → "uzbekistan" ham mos, lekin "xuzbek" emas.
    - whole_word=True (nom): "payme" → "payment" ga mos EMAS.
    - ".uz" kabi belgidan boshlanganlar: "day.uz" mos, ".uzum" emas.
    """
    esc = re.escape(keyword)
    left = r"(?<!\w)" if keyword[0].isalnum() else ""
    domain_like = not keyword[0].isalnum()  # ".uz" — domen oxiri, davomi bo'lmasligi kerak
    right = r"(?!\w)" if (whole_word or domain_like or not keyword[-1].isalnum()) else ""
    return re.compile(left + esc + right, re.IGNORECASE)


_UZ_PATTERNS = [(k, _kw_regex(k, whole_word=False)) for k in UZ_KEYWORDS]


def _is_uz(text: str) -> bool:
    return any(p.search(text) for _, p in _UZ_PATTERNS)


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
        link, title = getattr(e, "link", ""), getattr(e, "title", "").strip()
        if not link or not title:
            continue
        tm = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
        published = datetime.fromtimestamp(mktime(tm), tz=UTC) if tm else None
        items.append(EventItem(feed.name, title, link, _clean(getattr(e, "summary", "")),
                               published, feed.lang, feed.category))
    return items


async def _fetch_ransomware_live(client: httpx.AsyncClient, feed: Feed) -> list[EventItem]:
    resp = await client.get(f"https://api.ransomware.live/v2/countryvictims/{feed.url}")
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):  # rate-limit javobi ({"message": ...})
        raise RuntimeError(str(data))
    items: list[EventItem] = []
    for v in data:
        victim = (v.get("post_title") or v.get("victim") or "Noma'lum").strip()
        group = v.get("group_name") or v.get("group") or "?"
        activity = v.get("activity") or ""
        title = f"[{group}] {victim}" + (f" — {activity}" if activity else "")
        items.append(EventItem(
            source=feed.name,
            title=title,
            # .onion havolalar berilmaydi — ochiq ransomware.live sahifasi
            url=f"https://www.ransomware.live/group/{group.lower()}",
            summary=_clean(v.get("description") or ""),
            published=_parse_iso(v.get("discovered") or v.get("published")),
            lang=feed.lang,
            category=feed.category,
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
            summary=(f"🔎 {', '.join(hits[:4])} · " if hits else "") + snippet,
            published=m.date,
            lang=feed.lang,
            category=category_for(m.chat),
        ))
    return items


_FETCHERS = {
    "rss": _fetch_rss,
    "ransomware_live": _fetch_ransomware_live,
    "telegram": _fetch_telegram,
    "telegram_user": _fetch_telegram_user,
}

# ---------------------------------------------------------------- kesh
# feed.name -> (saqlangan vaqt, itemlar). Rate-limitli API'lar uchun muhim.
_cache: dict[str, tuple[float, list[EventItem]]] = {}


async def _fetch_cached(
    client: httpx.AsyncClient, feed: Feed, force: bool = False
) -> list[EventItem]:
    now = time.monotonic()
    cached = _cache.get(feed.name)
    # ransomware.live kabi rate-limitli manbalar uchun ttl force'da ham hurmat qilinadi
    min_age = feed.ttl if not force else min(feed.ttl, 60)
    if cached and now - cached[0] < min_age:
        return cached[1]
    fetcher = _FETCHERS.get(feed.kind)
    if fetcher is None:
        return []
    try:
        items = await fetcher(client, feed)
    except Exception:
        # Xato bo'lsa eski keshni qaytaramiz (bo'lsa), aks holda bo'sh
        return cached[1] if cached else []
    if feed.uz_filter:
        items = [i for i in items if _is_uz(i.title + " " + i.summary)]
    _cache[feed.name] = (now, items)
    return items


async def collect_all(force: bool = True) -> list[EventItem]:
    """Barcha yoqilgan manbalardan hammasini yig'adi (fon yig'uvchi uchun)."""
    headers = {"User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=12.0, headers=headers, follow_redirects=True) as client:
        batches = await asyncio.gather(
            *(_fetch_cached(client, f, force=force) for f in enabled_feeds())
        )
    return [i for batch in batches for i in batch]


async def fetch_events(
    limit: int = 40, query: str | None = None, category: str | None = None
) -> list[EventItem]:
    feeds = enabled_feeds()
    headers = {"User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=12.0, headers=headers, follow_redirects=True) as client:
        batches = await asyncio.gather(*(_fetch_cached(client, f) for f in feeds))

    items = [i for batch in batches for i in batch]
    # Kategoriya natija darajasida (bitta manba bir nechta kategoriya berishi mumkin; kesh tufayli arzon)
    if category:
        items = [i for i in items if i.category == category]
    if query:
        q = query.lower()
        items = [i for i in items if q in i.title.lower() or q in i.summary.lower()]
    items.sort(key=lambda i: i.published or datetime.min.replace(tzinfo=UTC), reverse=True)
    return items[:limit]
