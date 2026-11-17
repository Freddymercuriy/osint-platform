"""ransomware.live PRO API — ransomware qurbonlari (davlat kodi bo'yicha), bepul shaxsiy kalit bilan.

Hujjat (joriy): https://api-pro.ransomware.live/docs  (swagger: https://api-pro.ransomware.live/swagger.json),
kalit: https://www.ransomware.live/my
- Baza: https://api-pro.ransomware.live ; autentifikatsiya: `X-API-KEY` sarlavhasi (kalitsiz → 401).
- Limit: 60 so'rov/daqiqa va 500 000 so'rov/oy (oshsa HTTP 429 + Retry-After).
- `GET /victims/?country=XX[&year=YYYY&month=MM]` — filtrlar AND; kamida bitta filtr shart; `year` faqat `month` bilan.
  Elementlar: victim, group, attackdate, discovered, country, activity, website, permalink, id, ...

config: {"countries": ["UZ", "KZ", "KG", "TJ", "TM"]}
state: {"last_discovered": ISO} — kursor; keyingi chaqiruvlarda faqat kursordan keyingi oylar so'raladi.
Elementlar legacy `ransomware_live` bilan bir xil (`victim_item`) — dedup_key mos keladi. `.onion` havolalar berilmaydi.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.connectors.base import (
    ConfigError, Connector, ConnectorError, FetchContext, FetchResult, RawItem, register,
)
from app.services.connectors.ransomware_live import CA_CODES, public_link, victim_item
from app.services.events.filters import _parse_iso

BASE = "https://api-pro.ransomware.live"


def _months(since: datetime, now: datetime) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = since.year, since.month
    while (y, m) <= (now.year, now.month) and len(out) < 24:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


@register
class RansomwareLiveProConnector(Connector):
    kind = "ransomware_live_pro"
    title = "ransomware.live PRO API"
    key = "required"
    default_key_env = "RANSOMWARE_LIVE_API_KEY"
    config_fields = ("countries",)

    def validate_config(self, config: dict) -> None:
        countries = config.get("countries")
        if countries is not None and (not isinstance(countries, list) or not all(isinstance(c, str) for c in countries)):
            raise ConfigError("countries — ISO-2 kodlar ro'yxati bo'lishi kerak")

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        codes = [c.strip().upper() for c in (ctx.source.config.get("countries") or CA_CODES) if c.strip()]
        now = datetime.now(UTC)
        cursor = None if ctx.dry_run else _parse_iso((ctx.source.state or {}).get("last_discovered"))
        since = (cursor - timedelta(days=1)) if cursor else now - timedelta(days=max(ctx.source.backfill_days or 30, 1))
        headers = {"X-API-KEY": ctx.api_key or "", "Accept": "application/json"}

        items: list[RawItem] = []
        newest = cursor
        status = 200
        for code in codes:
            for year, month in _months(since, now):
                try:
                    resp = await ctx.http.get(f"{BASE}/victims/", headers=headers,
                                              params={"country": code, "year": year, "month": f"{month:02d}"})
                except ConnectorError as exc:
                    if exc.http_status == 404:  # natija yo'q
                        continue
                    raise
                status = resp.status_code
                data = resp.json()
                if isinstance(data, dict):
                    data = data.get("victims") or data.get("data") or []
                if not isinstance(data, list):
                    raise ConnectorError(f"Kutilmagan javob: {str(data)[:200]}", http_status=status)
                for v in data:
                    if not isinstance(v, dict):
                        continue
                    country = (v.get("country") or code).strip().upper()
                    if country != code:
                        continue
                    discovered = _parse_iso(v.get("discovered")) or _parse_iso(v.get("attackdate"))
                    if cursor and discovered and discovered <= cursor:
                        continue
                    if discovered and (newest is None or discovered > newest):
                        newest = discovered
                    group = v.get("group") or "?"
                    activity = v.get("activity") or ""
                    if activity.lower() in ("not found", "unknown"):
                        activity = ""
                    items.append(victim_item(
                        victim=(v.get("victim") or "Noma'lum").strip(), group=group, country=country,
                        domain=(v.get("website") or v.get("domain") or "").strip().lower().rstrip("/"),
                        activity=activity, description=v.get("description") or "", discovered=discovered,
                        link=public_link(v.get("permalink") or "", group), source="ransomware.live",
                    ))
        state = None if ctx.dry_run or not newest else {"last_discovered": newest.isoformat()}
        return FetchResult(items, status, state=state)
