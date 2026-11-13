from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from time import mktime

import feedparser
import httpx

from app.services.events.feeds import Feed, enabled_feeds

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


def _parse_published(entry) -> datetime | None:
    tm = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if tm is None:
        return None
    try:
        return datetime.fromtimestamp(mktime(tm), tz=UTC)
    except (ValueError, OverflowError):
        return None


def _clean(text: str, limit: int = 280) -> str:
    # HTML teglarini soddagina olib tashlaymiz
    import re

    text = re.sub(r"<[^>]+>", "", text or "").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


async def _fetch_feed(client: httpx.AsyncClient, feed: Feed) -> list[EventItem]:
    try:
        resp = await client.get(feed.url)
        resp.raise_for_status()
    except httpx.HTTPError:
        return []

    # feedparser sinxron — event loop'ni bloklamaslik uchun thread'da
    parsed = await asyncio.to_thread(feedparser.parse, resp.content)
    items: list[EventItem] = []
    for entry in parsed.entries:
        link = getattr(entry, "link", "")
        title = getattr(entry, "title", "").strip()
        if not link or not title:
            continue
        items.append(
            EventItem(
                source=feed.name,
                title=title,
                url=link,
                summary=_clean(getattr(entry, "summary", "")),
                published=_parse_published(entry),
                lang=feed.lang,
                category=feed.category,
            )
        )
    return items


async def fetch_events(limit: int = 40, query: str | None = None) -> list[EventItem]:
    """Barcha yoqilgan feedlardan yangiliklarni yig'adi, saralaydi.

    query berilsa — sarlavha/qisqacha matnda shu so'z bo'yicha filtr.
    """
    feeds = enabled_feeds()
    headers = {"User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=10.0, headers=headers, follow_redirects=True) as client:
        batches = await asyncio.gather(*(_fetch_feed(client, f) for f in feeds))

    items = [item for batch in batches for item in batch]

    if query:
        q = query.lower()
        items = [i for i in items if q in i.title.lower() or q in i.summary.lower()]

    # Yangilari yuqorida (sanasi yo'qlar oxirida)
    items.sort(key=lambda i: i.published or datetime.min.replace(tzinfo=UTC), reverse=True)
    return items[:limit]
