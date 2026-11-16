"""Cloudflare Radar — internet uzilishlari (outage annotations), davlat bo'yicha.

Hujjat: https://developers.cloudflare.com/api/operations/radar-get-annotations-outages
`GET https://api.cloudflare.com/client/v4/radar/annotations/outages` — `location` (alpha-2), `dateStart`,
`dateEnd`, `dateRange`, `limit`, `offset`; javob `{"result": {"annotations": [...]}}`. Auth: `Authorization: Bearer <token>`.
Cloudflare umumiy API limiti: 1200 so'rov / 5 daqiqa. Hujjat havolasi: https://radar.cloudflare.com/outage-center
Hujum trendlari (layer3/7) — qo'shilmagan (endpoint/javob shakli tasdiqlanmagan).

config: {"countries": ["UZ","KZ","KG","TJ","TM"], "limit": 50}; state: {"last_run": iso}
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.connectors.base import (
    AuthMissing, Connector, ConnectorError, FetchContext, FetchResult, RawItem, register,
)
from app.services.events.filters import _clean, _parse_iso

API = "https://api.cloudflare.com/client/v4/radar/annotations/outages"
OUTAGE_CENTER = "https://radar.cloudflare.com/outage-center"
CA_CODES = ("UZ", "KZ", "KG", "TJ", "TM")
OVERLAP_DAYS = 7  # davom etayotgan uzilishga keyin endDate qo'shiladi — oxirgi haftani qayta o'qiymiz


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@register
class CloudflareRadarConnector(Connector):
    kind = "cloudflare_radar"
    title = "Cloudflare Radar outages"
    key = "required"
    default_key_env = "CLOUDFLARE_API_TOKEN"
    config_fields = ("countries",)

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        if not ctx.api_key:
            raise AuthMissing("CLOUDFLARE_API_TOKEN sozlanmagan")
        cfg = ctx.source.config or {}
        wanted = [c.strip().upper() for c in (cfg.get("countries") or CA_CODES) if c and c.strip()]
        limit = int(cfg.get("limit") or 50)
        now = datetime.now(UTC)
        last = None if ctx.dry_run else _parse_iso((ctx.source.state or {}).get("last_run"))
        start = (last - timedelta(days=OVERLAP_DAYS)) if last else now - timedelta(days=ctx.source.backfill_days or 14)

        by_id: dict[str, dict] = {}
        status = None
        for code in wanted:
            resp = await ctx.http.get(
                API, headers={"Authorization": f"Bearer {ctx.api_key}"},
                # dateEnd majburiy: faqat dateStart bilan API 400 qaytaradi ("The dateEnd must be after dateStart")
                params={"location": code, "dateStart": _iso(start), "dateEnd": _iso(now), "limit": limit,
                        "format": "JSON"},
            )
            status = resp.status_code
            body = resp.json()
            result = body.get("result") if isinstance(body, dict) else None
            if not isinstance(result, dict) or not isinstance(result.get("annotations"), list):
                raise ConnectorError("Radar: kutilmagan javob shakli", http_status=status)
            for ann in result["annotations"]:
                if isinstance(ann, dict) and ann.get("id"):
                    by_id.setdefault(str(ann["id"]), ann)

        items = [it for it in (self._item(a, set(wanted)) for a in by_id.values()) if it]
        return FetchResult(items, status, state=None if ctx.dry_run else {"last_run": _iso(now)})

    def _item(self, ann: dict, wanted: set[str]) -> RawItem | None:
        details = [d for d in (ann.get("locationsDetails") or []) if isinstance(d, dict)]
        names = {str(d.get("code", "")).upper(): d.get("name") for d in details}
        codes = [c for c in CA_CODES if c in wanted and (c in names or c in {str(x).upper() for x in ann.get("locations") or []})]
        if not codes:
            return None
        outage = ann.get("outage") if isinstance(ann.get("outage"), dict) else {}
        cause = str(outage.get("outageCause") or "UNKNOWN").replace("_", " ").lower()
        country = " / ".join(str(names.get(c) or c) for c in codes)
        link = ann.get("linkedUrl") if str(ann.get("linkedUrl") or "").startswith(("http://", "https://")) else OUTAGE_CENTER
        asns = [a for a in (ann.get("asns") or []) if isinstance(a, int)]
        return RawItem(
            title=f"Internet outage in {country}: {cause}", url=link,
            summary=_clean(ann.get("description") or "")[:600],
            published=_parse_iso(ann.get("startDate")), lang="en", category="ddos-outage", channel="api",
            scope="regional", countries=codes, dedup_key=f"radar-outage:{ann['id']}",
            extra={"template": "outage", "country": country, "scope": ann.get("scope"), "cause": cause,
                   "start": ann.get("startDate"), "end": ann.get("endDate"), "asns": asns[:20],
                   "event_type": ann.get("eventType"), "outage_type": outage.get("outageType"),
                   "radar_id": str(ann["id"])},
        )
