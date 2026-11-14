"""NVD CVE API 2.0 — faqat CRITICAL (CVSS v3/v4) yangi CVE'lar.

Endpoint: https://services.nvd.nist.gov/rest/json/cves/2.0 ; hujjat: https://nvd.nist.gov/developers/vulnerabilities
Kalit ixtiyoriy (`apiKey` sarlavhasi): kalitsiz 5 so'rov / 30 s, kalit bilan 50 / 30 s. Sana oralig'i ≤ 120 kun.
Kursor: state {"last_published": iso}. config: {"url": "..."} (ixtiyoriy)
"""

from __future__ import annotations

import asyncio
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
from app.services.events.filters import _parse_iso

DEFAULT_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
PAGE_SIZE = 2000
MAX_PAGES = 10
MAX_RANGE = timedelta(days=120)
# Sahifalar orasidagi pauza (s): kalitsiz 5/30 s → 6 s; kalit bilan 50/30 s → 0.6 s. Testlar 0 qiladi.
PAGE_PAUSE_NO_KEY = 6.0
PAGE_PAUSE_KEY = 0.6
_METRIC_KEYS = ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30")


def _fmt(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}"


def critical_score(cve: dict) -> tuple[float, str] | None:
    """(ball, CVSS versiyasi) — birinchi CRITICAL metrika (v4 → v3.1 → v3.0), yo'q bo'lsa None."""
    metrics = cve.get("metrics") or {}
    for key in _METRIC_KEYS:
        for m in metrics.get(key) or []:
            d = m.get("cvssData") or {}
            if str(d.get("baseSeverity") or m.get("baseSeverity") or "").upper() == "CRITICAL":
                return float(d.get("baseScore") or 0), str(d.get("version") or key[-2:])
    return None


def vendor_product(cve: dict) -> tuple[str, str]:
    def walk(nodes):
        for n in nodes or []:
            for m in n.get("cpeMatch") or []:
                parts = str(m.get("criteria") or "").split(":")
                if m.get("vulnerable") and len(parts) > 4 and parts[3] not in ("", "*"):
                    return parts[3].replace("_", " "), parts[4].replace("_", " ")
            found = walk(n.get("nodes"))
            if found:
                return found
        return None

    found = walk(cve.get("configurations"))
    if found:
        return found
    for aff in cve.get("affected") or []:
        for d in aff.get("affectedData") or []:
            if d.get("vendor"):
                return str(d["vendor"]), str(d.get("product") or "")
    return "", ""


def english_description(cve: dict) -> str:
    descs = cve.get("descriptions") or []
    for d in descs:
        if str(d.get("lang", "")).lower().startswith("en"):
            return str(d.get("value") or "")
    return str(descs[0].get("value") or "") if descs else ""


@register
class NvdCvesConnector(Connector):
    kind = "nvd_cves"
    title = "NVD — critical CVEs"
    key = "optional"
    default_key_env = "NVD_API_KEY"
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
        url = src.config.get("url") or DEFAULT_URL
        now = datetime.now(UTC)
        cursor = None if ctx.dry_run else _parse_iso((src.state or {}).get("last_published"))
        start = max(cursor or now - timedelta(days=src.backfill_days), now - MAX_RANGE + timedelta(minutes=5))
        headers = {"Accept": "application/json"}
        if ctx.api_key:
            headers["apiKey"] = ctx.api_key
        pause = PAGE_PAUSE_KEY if ctx.api_key else PAGE_PAUSE_NO_KEY

        items: list[RawItem] = []
        newest = cursor
        index, status, truncated = 0, None, False
        for page in range(MAX_PAGES):
            if page:
                await asyncio.sleep(pause)
            resp = await ctx.http.get(url, headers=headers, params={
                "cvssV3Severity": "CRITICAL", "pubStartDate": _fmt(start), "pubEndDate": _fmt(now),
                "resultsPerPage": PAGE_SIZE, "startIndex": index,
            })
            status = resp.status_code
            try:
                data = resp.json()
                vulns = data.get("vulnerabilities") or []
                total = int(data.get("totalResults") or 0)
            except (ValueError, AttributeError, TypeError) as exc:
                raise ConnectorError("NVD: JSON o'qilmadi", http_status=status) from exc
            for v in vulns:
                cve = v.get("cve") if isinstance(v, dict) else None
                if not cve or not cve.get("id"):
                    continue
                published = _parse_iso(cve.get("published"))
                score = critical_score(cve)
                if not published or not score or (cursor and published <= cursor):
                    continue
                if newest is None or published > newest:
                    newest = published
                items.append(self._item(cve, published, score))
            index += len(vulns)
            if not vulns or index >= total:
                break
        else:
            truncated = True

        items.sort(key=lambda i: i.published)
        state = None if ctx.dry_run or truncated or newest is None else {"last_published": newest.isoformat()}
        note = "NVD: sahifalar chegarasi (MAX_PAGES) — kursor yangilanmadi" if truncated else None
        return FetchResult(items, status, state=state, note=note)

    @staticmethod
    def _item(cve: dict, published: datetime, score: tuple[float, str]) -> RawItem:
        cid = cve["id"]
        desc = english_description(cve).strip()
        vendor, product = vendor_product(cve)
        extra = {
            "template": "cve", "cve_id": cid, "vendor": vendor, "product": product,
            "cvss": score[0], "cvss_version": score[1], "kev": bool(cve.get("cisaExploitAdd")),
            "due_date": cve.get("cisaActionDue"),
        }
        return RawItem(
            title=f"{cid}: {' '.join(desc.split())[:160] or 'no description'}",
            url=f"https://nvd.nist.gov/vuln/detail/{cid}", summary=clip(desc), published=published,
            lang="en", category="vulnerability", channel="api", scope="global", severity="critical",
            extra=extra, dedup_key=f"cve:{cid}",
        )
