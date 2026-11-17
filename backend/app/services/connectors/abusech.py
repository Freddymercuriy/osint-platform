"""abuse.ch: URLhaus (zararli URL'lar) va ThreatFox (IOC'lar) — Markaziy Osiyo domenlari bo'yicha.

Ikkalasi ham bepul `Auth-Key` talab qiladi (https://auth.abuse.ch/), kalit `Auth-Key` sarlavhasida yuboriladi.
Hujjat: https://urlhaus-api.abuse.ch/  va  https://threatfox.abuse.ch/api/  (adolatli foydalanish qoidalari amal qiladi).
Zararli URL'ga hech qachon so'rov yuborilmaydi; item havolasi — abuse.ch hisobot sahifasi; query string saqlanmaydi.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from app.services.connectors.base import (
    AuthMissing, ConfigError, Connector, ConnectorError, FetchContext, FetchResult, RawItem, register,
)
from app.services.connectors.indicators import (
    defang, host_of, is_ip, parse_abusech_ts, safe_url, tld_country,
)

URLHAUS_RECENT = "https://urlhaus-api.abuse.ch/v1/urls/recent/"  # oxirgi 3 kun, ko'pi bilan 1000 ta
THREATFOX_API = "https://threatfox-api.abuse.ch/api/v1/"  # get_iocs: days 1..7
THREATFOX_IOC_PAGE = "https://threatfox.abuse.ch/ioc/{id}/"
_COUNTRY_KEYS = ("country", "country_code", "countrycode", "geo")


def _require_key(ctx: FetchContext) -> dict[str, str]:
    if not ctx.api_key:
        raise AuthMissing("abuse.ch Auth-Key sozlanmagan")
    return {"Auth-Key": ctx.api_key, "Accept": "application/json"}


def _json(resp) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError as exc:
        raise ConnectorError("abuse.ch: JSON emas", http_status=resp.status_code) from exc
    if not isinstance(data, dict):
        raise ConnectorError(f"Kutilmagan javob: {str(data)[:200]}", http_status=resp.status_code)
    return data


def _check_status(data: dict[str, Any], http_status: int) -> bool:
    """True — natijalar bor; False — bo'sh (no_results). Aks holda xato."""
    status = str(data.get("query_status") or "")
    if status == "ok":
        return True
    if status in ("no_result", "no_results"):
        return False
    if "auth" in status or "unauthor" in status or "key" in status:
        raise AuthMissing(f"abuse.ch kalitni rad etdi ({status})", http_status=http_status)
    raise ConnectorError(f"abuse.ch: query_status={status or '?'}", http_status=http_status)


@register
class URLhausConnector(Connector):
    kind = "urlhaus"
    title = "abuse.ch URLhaus (zararli URL, .uz/.kz/.kg/.tj/.tm)"
    key = "required"
    default_key_env = "ABUSECH_AUTH_KEY"
    config_fields = ("limit",)

    def validate_config(self, config: dict) -> None:
        limit = config.get("limit")
        if limit is not None and not (isinstance(limit, int) and 1 <= limit <= 1000):
            raise ConfigError("limit 1..1000 oralig'idagi butun son bo'lishi kerak")

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        headers = _require_key(ctx)
        limit = ctx.source.config.get("limit")
        url = URLHAUS_RECENT + (f"limit/{int(limit)}/" if limit else "")
        resp = await ctx.http.get(url, headers=headers)
        data = _json(resp)
        if not _check_status(data, resp.status_code):
            return FetchResult([], resp.status_code)
        items: list[RawItem] = []
        for row in data.get("urls") or []:
            item = self._item(row)
            if item:
                items.append(item)
        return FetchResult(items, resp.status_code)

    @staticmethod
    def _item(row: dict[str, Any]) -> RawItem | None:
        clean = safe_url(row.get("url") or "")
        if not clean:
            return None
        host = host_of(clean)
        country = tld_country(host)
        if not country:
            return None
        tags = [str(t) for t in (row.get("tags") or []) if t]
        threat = ", ".join(tags) or str(row.get("threat") or "malware_download")
        ref = str(row.get("urlhaus_reference") or "").strip()
        if not ref.startswith("https://urlhaus.abuse.ch/"):
            rid = str(row.get("id") or "").strip()
            if not rid:
                return None
            ref = f"https://urlhaus.abuse.ch/url/{rid}/"
        ioc = defang(clean)
        status = str(row.get("url_status") or "unknown")
        return RawItem(
            title=f"Malware URL on {host} ({threat})",
            url=ref,
            summary=f"URLhaus: {ioc} — status: {status}"[:600],
            published=parse_abusech_ts(row.get("date_added")),
            lang="en", category="malware", channel="api", scope="regional", countries=[country],
            extra={"template": "indicator", "ioc_type": "url", "ioc": ioc, "host": host, "threat": threat,
                   "url_status": status},
            dedup_key=f"ioc:url:{clean}",
        )


@register
class ThreatFoxConnector(Connector):
    kind = "threatfox"
    title = "abuse.ch ThreatFox (IOC, .uz/.kz/.kg/.tj/.tm)"
    key = "required"
    default_key_env = "ABUSECH_AUTH_KEY"
    config_fields = ("days",)

    def validate_config(self, config: dict) -> None:
        days = config.get("days")
        if days is not None and not (isinstance(days, int) and 1 <= days <= 7):
            raise ConfigError("days 1..7 oralig'idagi butun son bo'lishi kerak")

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        headers = _require_key(ctx)
        days = ctx.source.config.get("days")
        if not days:
            days = max(1, min(7, ctx.source.backfill_days or 1))
            last = None if ctx.dry_run else (ctx.source.state or {}).get("last_seen")
            if last:
                try:
                    age = datetime.now(UTC) - datetime.fromisoformat(last)
                    days = max(1, min(7, math.ceil(age.total_seconds() / 86400) + 1))
                except ValueError:
                    pass
        resp = await ctx.http.post(THREATFOX_API, headers=headers, json={"query": "get_iocs", "days": int(days)})
        data = _json(resp)
        if not _check_status(data, resp.status_code):
            return FetchResult([], resp.status_code)
        items: list[RawItem] = []
        newest: datetime | None = None
        for row in data.get("data") or []:
            item = self._item(row)
            if item:
                items.append(item)
                if item.published and (newest is None or item.published > newest):
                    newest = item.published
        state = {"last_seen": newest.isoformat()} if newest and not ctx.dry_run else None
        return FetchResult(items, resp.status_code, state=state)

    @staticmethod
    def _item(row: dict[str, Any]) -> RawItem | None:
        raw_ioc = str(row.get("ioc") or "").strip()
        raw_type = str(row.get("ioc_type") or "").lower()
        rid = str(row.get("id") or "").strip()
        if not raw_ioc or not rid:
            return None
        if raw_type == "url":
            clean = safe_url(raw_ioc)
            if not clean:
                return None
            host, ioc_type, value = host_of(clean), "url", clean
            country = tld_country(host)
        elif raw_type == "domain":
            host, ioc_type = host_of(raw_ioc), "domain"
            value, country = host, tld_country(host)
        elif raw_type.startswith("ip"):
            host, ioc_type, value = host_of(raw_ioc), "ip", raw_ioc.split("/")[0]
            if not is_ip(host):
                return None
            # IP: faqat API o'zi davlatni bildirsa (geolokatsiya qilinmaydi)
            country = None
            for key in _COUNTRY_KEYS:
                code = str(row.get(key) or "").strip().upper()
                if code in ("UZ", "KZ", "KG", "TJ", "TM"):
                    country = code
                    break
        else:
            return None
        if not country or not host:
            return None
        threat = str(row.get("malware_printable") or row.get("malware") or "unknown")
        ioc = defang(value)
        conf = row.get("confidence_level")
        tag = f" ({row.get('threat_type')})" if row.get("threat_type") else ""
        return RawItem(
            title=f"Malware IOC on {host} ({threat})",
            url=THREATFOX_IOC_PAGE.format(id=rid),
            summary=f"ThreatFox {ioc_type}: {ioc} — {threat}{tag}, confidence {conf}"[:600],
            published=parse_abusech_ts(row.get("first_seen")),
            lang="en", category="malware", channel="api", scope="regional", countries=[country],
            extra={"template": "indicator", "ioc_type": ioc_type, "ioc": ioc, "host": host, "threat": threat,
                   "confidence": conf},
            dedup_key=f"ioc:{ioc_type}:{value}",
        )
