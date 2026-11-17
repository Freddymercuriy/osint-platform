"""Have I Been Pwned — ommaviy buzilishlar (breach) katalogi: GET https://haveibeenpwned.com/api/v3/breaches.

Kalitsiz; faqat buzilish metadatasi (nom, domen, soni, ma'lumot toifalari). Hisob (akkaunt) ma'lumotlari
(`breachedaccount`, `pastes`) HECH QACHON so'ralmaydi. Hujjat: https://haveibeenpwned.com/API/v3#AllBreaches
config: {"url": "..."} (ixtiyoriy)
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

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
from app.services.events.filters import _clean, _parse_iso
from app.services.events.geo import detect_countries

DEFAULT_URL = "https://haveibeenpwned.com/api/v3/breaches"
REGION_TLDS = {"uz": "UZ", "kz": "KZ", "kg": "KG", "tj": "TJ", "tm": "TM"}
SUMMARY_LIMIT = 600


def clip(text: str, limit: int = SUMMARY_LIMIT) -> str:
    text = _clean(re.sub(r"<[^>]*$", "", text or ""), limit=10**6)  # kesilgan oxirgi teg ham tashlanadi
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def domain_country(domain: str | None) -> str | None:
    tld = (domain or "").strip().lower().rstrip(".").rsplit(".", 1)[-1]
    return REGION_TLDS.get(tld) if "." in (domain or "") else None


@register
class HibpBreachesConnector(Connector):
    kind = "hibp_breaches"
    title = "Have I Been Pwned — breaches"
    key = None
    config_fields = ("url",)

    def validate_config(self, config: dict) -> None:
        url = (config or {}).get("url")
        if url and not str(url).startswith(("http://", "https://")):
            raise ConfigError("config.url — http(s) manzil bo'lishi kerak")

    def target_urls(self, source: SourceView) -> list[str]:
        return [source.config.get("url") or DEFAULT_URL]

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        src = ctx.source
        self.validate_config(src.config)
        resp = await ctx.http.get(
            src.config.get("url") or DEFAULT_URL,
            headers={"Accept": "application/json"},
            etag=None if ctx.dry_run else src.etag,
            last_modified=None if ctx.dry_run else src.last_modified,
            allow_not_modified=True,
        )
        if resp.status_code == 304:
            return FetchResult([], 304, etag=src.etag, last_modified=src.last_modified, not_modified=True)
        try:
            data = resp.json()
        except ValueError as exc:
            raise ConnectorError("HIBP: JSON o'qilmadi", http_status=resp.status_code) from exc
        if not isinstance(data, list):
            raise ConnectorError("HIBP: kutilmagan javob shakli", http_status=resp.status_code)

        cursor = None if ctx.dry_run else _parse_iso((src.state or {}).get("last_added"))
        cutoff = cursor or datetime.now(UTC) - timedelta(days=src.backfill_days)
        newest = cursor
        items: list[RawItem] = []
        for b in data:
            if not isinstance(b, dict) or b.get("IsSpamList") or b.get("IsFabricated") or b.get("IsRetired"):
                continue
            added = _parse_iso(b.get("AddedDate"))
            name = (b.get("Name") or "").strip()
            if not added or not name or added <= cutoff:
                continue
            if newest is None or added > newest:
                newest = added
            items.append(self._item(b, name, added))
        items.sort(key=lambda i: i.published)  # eskidan yangiga
        state = None if ctx.dry_run or newest is None else {"last_added": newest.isoformat()}
        return FetchResult(items, resp.status_code, etag=resp.headers.get("etag"),
                           last_modified=resp.headers.get("last-modified"), state=state)

    @staticmethod
    def _item(b: dict, name: str, added: datetime) -> RawItem:
        title = (b.get("Title") or name).strip()
        domain = (b.get("Domain") or "").strip().lower()
        count = int(b.get("PwnCount") or 0)
        desc = clip(b.get("Description") or "")
        countries: list[str] = []
        by_tld = domain_country(domain)
        if by_tld:
            countries.append(by_tld)
        for code in detect_countries(title, desc):
            if code not in countries:
                countries.append(code)
        classes = [str(c) for c in (b.get("DataClasses") or []) if isinstance(c, str)]
        extra = {
            "template": "breach", "breach_name": name, "domain": domain, "pwn_count": count,
            "data_classes": classes, "breach_date": b.get("BreachDate"),
            "is_verified": bool(b.get("IsVerified")), "is_sensitive": bool(b.get("IsSensitive")),
        }
        return RawItem(
            title=f"{title}: {count:,} accounts breached",
            url=f"https://haveibeenpwned.com/PwnedWebsites#{name}",
            summary=desc, published=added, lang="en", category="leak", channel="api",
            scope="regional" if countries else "global", countries=countries, extra=extra,
            dedup_key=f"hibp:{name.lower()}",
        )
