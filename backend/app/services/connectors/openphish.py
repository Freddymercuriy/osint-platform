"""OpenPhish community feed — oddiy matn ro'yxati (har qatorda bitta phishing URL).

`https://openphish.com/feed.txt` hozir GitHub'dagi `openphish/public_feed` ga 302 qiladi (ETag bor, Cache-Control 300 s);
bepul community lenta bir necha soatda yangilanadi, shuning uchun so'rov oralig'i >= 6 soat.
Qoldiriladi: milliy domen (.uz .kz .kg .tj .tm) yoki xost/path'da `TG_EXTRA_KEYWORDS` brendi bor URL'lar.

Item havolasi: OpenPhish'da alohida URL sahifasi yo'q. Phishing URL'ning o'ziga havola BERILMAYDI. Havola —
`https://urlscan.io/domain/<host>` (urlscan passiv arxiv: sahifani ochmaydi; faqat xost) + `#ioc-<sha1[:12]>`
fragmenti: server'ga yuborilmaydi, lekin bir xostdagi turli URL'lar uchun `uid` (source|url|title) to'qnashmasin.
Query string / fragment / userinfo saqlanmaydi (qurbon email'lari bo'lishi mumkin).
"""

from __future__ import annotations

import hashlib
import re

from app.core.config import settings
from app.services.connectors.base import ConfigError, Connector, FetchContext, FetchResult, RawItem, register
from app.services.connectors.indicators import defang, host_of, is_ip, safe_url, tld_country

FEED_URL = "https://openphish.com/feed.txt"
MAX_LINES = 20000


def brand_pattern(brand: str) -> re.Pattern[str]:
    """Butun so'z (harf/raqam chegarasi) bo'yicha moslik; ko'p so'zli brend ('xalq banki') ajratgichga sezgir emas."""
    words = [re.escape(w) for w in re.split(r"\W+", brand.lower()) if w]
    return re.compile(r"(?<![a-z0-9])" + r"[^a-z0-9]*".join(words) + r"(?![a-z0-9])")


def match_brand(text: str, brands: list[str]) -> str | None:
    text = text.lower()
    for brand in brands:
        if re.sub(r"\W+", "", brand) and brand_pattern(brand).search(text):
            return brand
    return None


def safe_link(host: str, clean_url: str) -> str:
    kind = "ip" if is_ip(host) else "domain"
    return f"https://urlscan.io/{kind}/{host.strip('[]')}#ioc-{hashlib.sha1(clean_url.encode()).hexdigest()[:12]}"


@register
class OpenPhishConnector(Connector):
    kind = "openphish"
    title = "OpenPhish community feed (phishing URL)"
    config_fields = ("url",)

    def validate_config(self, config: dict) -> None:
        url = config.get("url")
        if url is not None and not str(url).startswith("https://"):
            raise ConfigError("url https:// bilan boshlanishi kerak")

    def target_urls(self, source) -> list[str]:
        url = (source.config or {}).get("url")
        return [url] if url else []

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        url = ctx.source.config.get("url") or FEED_URL
        etag = None if ctx.dry_run else ctx.source.etag
        modified = None if ctx.dry_run else ctx.source.last_modified
        resp = await ctx.http.get(url, etag=etag, last_modified=modified, allow_not_modified=True)
        if resp.status_code == 304:
            return FetchResult([], 304, not_modified=True)
        # config.brands — shu manba uchun aniq brendlar ro'yxati (TG_EXTRA_KEYWORDS da umumiy so'zlar ham bor:
        # "egov", shahar nomlari — global lentada yolg'on "mintaqaviy" mos kelish beradi)
        brands = [b.strip().lower() for b in (ctx.source.config.get("brands") or settings.tg_extra_keywords_list)
                  if str(b).strip()]
        items: list[RawItem] = []
        seen: set[str] = set()
        for line in resp.text.splitlines()[:MAX_LINES]:
            item = self._item(line.strip(), brands)
            if item and item.dedup_key not in seen:
                seen.add(item.dedup_key or "")
                items.append(item)
        return FetchResult(items, resp.status_code, etag=resp.headers.get("etag"),
                           last_modified=resp.headers.get("last-modified"))

    @staticmethod
    def _item(line: str, brands: list[str]) -> RawItem | None:
        if not line or " " in line or not line.lower().startswith(("http://", "https://")):
            return None
        clean = safe_url(line)
        if not clean:
            return None
        host = host_of(clean)
        country = tld_country(host)
        brand = match_brand(clean.split("://", 1)[1], brands) if brands else None
        if not country and not brand:
            return None
        title = f"Phishing URL on {host}" + (f" targeting {brand}" if brand else "")
        ioc = defang(clean)
        return RawItem(
            title=title, url=safe_link(host, clean), summary=f"OpenPhish: {ioc}"[:600],
            lang="en", category="phishing", channel="api", scope="regional",
            countries=[country] if country else [],
            extra={"template": "indicator", "ioc_type": "url", "ioc": ioc, "host": host,
                   "threat": "phishing", "brand": brand},
            dedup_key=f"ioc:url:{clean}",
        )
