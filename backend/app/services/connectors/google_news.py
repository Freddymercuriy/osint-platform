"""Google News RSS qidiruvi — bot-himoyasi tufayli to'g'ridan-to'g'ri o'qib bo'lmaydigan saytlar uchun ikkilamchi manba.

config: {"query": "site:example.com (Uzbekistan OR Kazakhstan) when:7d"}
Saytning o'ziga murojaat qilinmaydi: faqat Google indeksidagi sarlavha, nashr nomi, sana va Google havolasi.
"""

from __future__ import annotations

from app.services.connectors.base import ConfigError, Connector, FetchContext, FetchResult, RawItem, register
from app.services.connectors.rss import entry_time, parse_feed
from app.services.events.filters import _unescape

GOOGLE_NEWS_TAG = "(Google News)"
# til → (hl, gl, ceid)
_EDITION = {"ru": ("ru", "KZ", "KZ:ru"), "en": ("en-US", "US", "US:en")}


@register
class GoogleNewsConnector(Connector):
    kind = "google_news"
    title = "Google News RSS qidiruvi"
    config_fields = ("query",)

    def validate_config(self, config: dict) -> None:
        if not ((config or {}).get("query") or "").strip():
            raise ConfigError("config.query — Google News qidiruv so'rovi kerak")

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        src = ctx.source
        self.validate_config(src.config)
        hl, gl, ceid = _EDITION.get(src.lang, _EDITION["en"])
        resp = await ctx.http.get(
            "https://news.google.com/rss/search",
            params={"q": src.config["query"], "hl": hl, "gl": gl, "ceid": ceid},
        )
        parsed = await parse_feed(resp.content)
        items: list[RawItem] = []
        for e in parsed.entries:
            link, title = getattr(e, "link", "") or "", _unescape(getattr(e, "title", "") or "").strip()
            if not link or not title:
                continue
            s = getattr(e, "source", None)
            outlet = _unescape((s.get("title") if s else "") or "").strip() or src.name
            if title.endswith(f" - {outlet}"):  # Google sarlavha oxiriga " - Nashr" qo'shadi
                title = title[: -len(outlet) - 3].rstrip()
            # description — faqat sarlavhaning takrori, shuning uchun summary bo'sh
            items.append(RawItem(title=title, url=link, published=entry_time(e),
                                 source_name=f"{outlet} {GOOGLE_NEWS_TAG}"[:128]))
        return FetchResult(items, resp.status_code)
