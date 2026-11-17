"""RSS / Atom lenta. config: {"url": "https://..."}"""

from __future__ import annotations

import asyncio
from calendar import timegm  # feedparser struct_time'lari UTC'da — mktime (lokal vaqt) emas
from datetime import UTC, datetime

import feedparser

from app.services.connectors.base import (
    ConfigError,
    ConnectorError,
    Connector,
    FetchContext,
    FetchResult,
    RawItem,
    SourceView,
    register,
)
from app.services.events.filters import _clean, _unescape


def entry_time(e) -> datetime | None:
    tm = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
    return datetime.fromtimestamp(timegm(tm), tz=UTC) if tm else None


async def parse_feed(content: bytes):
    parsed = await asyncio.to_thread(feedparser.parse, content)
    if not parsed.entries and getattr(parsed, "bozo", False):
        raise ConnectorError(f"RSS/Atom o'qilmadi: {type(parsed.get('bozo_exception')).__name__}")
    return parsed


@register
class RssConnector(Connector):
    kind = "rss"
    title = "RSS / Atom"
    config_fields = ("url",)

    def validate_config(self, config: dict) -> None:
        url = (config or {}).get("url") or ""
        if not url.startswith(("http://", "https://")):
            raise ConfigError("config.url — http(s) manzil bo'lishi kerak")

    def target_urls(self, source: SourceView) -> list[str]:
        return [source.config.get("url", "")]

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        src = ctx.source
        self.validate_config(src.config)
        resp = await ctx.http.get(
            src.config["url"],
            etag=None if ctx.dry_run else src.etag,
            last_modified=None if ctx.dry_run else src.last_modified,
            allow_not_modified=True,
        )
        if resp.status_code == 304:
            return FetchResult([], 304, etag=src.etag, last_modified=src.last_modified, not_modified=True)
        parsed = await parse_feed(resp.content)
        items: list[RawItem] = []
        for e in parsed.entries:
            link, title = getattr(e, "link", "") or "", _unescape(getattr(e, "title", "") or "").strip()
            if not link or not title:
                continue
            items.append(RawItem(
                title=title, url=link.strip(), summary=_clean(getattr(e, "summary", "") or ""),
                published=entry_time(e),
            ))
        return FetchResult(items, resp.status_code, etag=resp.headers.get("etag"),
                           last_modified=resp.headers.get("last-modified"))
