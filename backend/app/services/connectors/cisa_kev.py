"""CISA Known Exploited Vulnerabilities (KEV) — GitHub ko'zgusi cisagov/kev-data (ommaviy, kalitsiz).

Manba: https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json
Kursor: state {"last_added": "YYYY-MM-DD", "seen": [shu sanadagi CVE'lar]} — kun ichida keyin qo'shilganlar ham tushadi.
config: {"url": "..."} (ixtiyoriy)
"""

from __future__ import annotations

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
from app.services.connectors.hibp import clip

DEFAULT_URL = "https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json"


def _date(value: str | None):
    try:
        return datetime.strptime((value or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


@register
class CisaKevConnector(Connector):
    kind = "cisa_kev"
    title = "CISA Known Exploited Vulnerabilities"
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
            etag=None if ctx.dry_run else src.etag,
            last_modified=None if ctx.dry_run else src.last_modified,
            allow_not_modified=True,
        )
        if resp.status_code == 304:
            return FetchResult([], 304, etag=src.etag, last_modified=src.last_modified, not_modified=True)
        try:
            data = resp.json()
            vulns = data["vulnerabilities"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ConnectorError("KEV: JSON o'qilmadi", http_status=resp.status_code) from exc

        state = {} if ctx.dry_run else (src.state or {})
        last = _date(state.get("last_added"))
        seen = set(state.get("seen") or []) if last else set()
        floor = last or (datetime.now(UTC) - timedelta(days=src.backfill_days)).date()

        fresh: list[tuple] = []
        for v in vulns:
            if not isinstance(v, dict) or not v.get("cveID"):
                continue
            added = _date(v.get("dateAdded"))
            if not added:
                continue
            if last:
                if added < last or (added == last and v["cveID"] in seen):
                    continue
            elif added < floor:
                continue
            fresh.append((added, v))
        fresh.sort(key=lambda t: (t[0], t[1]["cveID"]))
        items = [self._item(v, added) for added, v in fresh]

        new_state = None
        if fresh and not ctx.dry_run:
            top = fresh[-1][0]
            ids = {v["cveID"] for a, v in fresh if a == top}
            if last == top:
                ids |= seen
            new_state = {"last_added": top.isoformat(), "seen": sorted(ids)}
        return FetchResult(items, resp.status_code, etag=resp.headers.get("etag"),
                           last_modified=resp.headers.get("last-modified"), state=new_state)

    @staticmethod
    def _item(v: dict, added) -> RawItem:
        cve = v["cveID"]
        vendor, product = (v.get("vendorProject") or "").strip(), (v.get("product") or "").strip()
        ransomware = v.get("knownRansomwareCampaignUse") or "Unknown"
        extra = {
            "template": "cve", "cve_id": cve, "vendor": vendor, "product": product, "kev": True,
            "due_date": v.get("dueDate"), "ransomware_use": ransomware, "cwes": list(v.get("cwes") or []),
            "vulnerability_name": v.get("vulnerabilityName"),
        }
        return RawItem(
            title=f"{cve}: {vendor} {product} — {v.get('vulnerabilityName') or ''}".rstrip(" —"),
            url=f"https://nvd.nist.gov/vuln/detail/{cve}",
            summary=clip(v.get("shortDescription") or ""),
            published=datetime(added.year, added.month, added.day, tzinfo=UTC),
            lang="en", category="vulnerability", channel="api", scope="global",
            severity="critical" if ransomware == "Known" else "high", extra=extra,
            dedup_key=f"cve:{cve}",
        )
