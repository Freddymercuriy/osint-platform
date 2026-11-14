"""RansomLook — ochiq ransomware tracker (kalitsiz).

Hujjat: https://www.ransomlook.io/doc (swagger: https://www.ransomlook.io/swagger.json).
`GET /api/recent/{N}` — oxirgi N post (default 100): post_title, group_name, discovered (UTC, "YYYY-MM-DD HH:MM:SS.ffffff"),
description, link (nisbiy yo'l yoki null). Davlat va domen maydoni YO'Q — davlat milliy domen (.uz .kz .kg .tj .tm) yoki
sarlavha/tavsifdagi davlat nomi bo'yicha aniqlanadi (`geo.detect_countries`). Rasmiy limit hujjatda yozilmagan.

config: {"countries": [...], "limit": 100}
Havola — ransomlook.io dagi ommaviy sahifa; `.onion` hech qachon berilmaydi. Elementlar `victim_item` bilan
(ransomware.live bilan bir xil dedup_key).
"""

from __future__ import annotations

import re

from app.services.connectors.base import ConfigError, Connector, ConnectorError, FetchContext, FetchResult, RawItem, register
from app.services.connectors.ransomware_live import CA_CODES, victim_item
from app.services.events.filters import _parse_iso
from app.services.events.geo import detect_countries

SITE = "https://www.ransomlook.io"
_DOMAIN_RE = re.compile(r"(?<![\w.-])((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,24})(?![\w-])", re.I)


def extract_domain(title: str) -> str:
    """Sarlavhadagi birinchi domenga o'xshash so'z (masalan "Acme (acme.kz)")."""
    m = _DOMAIN_RE.search((title or "").replace("%20", " "))
    return m.group(1).lower() if m else ""


def post_link(link: str | None, group: str) -> str:
    if link and link.startswith("/") and not link.startswith("//") and ".onion" not in link:
        return SITE + link
    return f"{SITE}/group/{group}"


@register
class RansomLookConnector(Connector):
    kind = "ransomlook"
    title = "RansomLook (recent posts)"
    config_fields = ("countries", "limit")

    def validate_config(self, config: dict) -> None:
        limit = config.get("limit", 100)
        if not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ConfigError("limit 1..500 oralig'ida bo'lishi kerak")

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        codes = {c.strip().upper() for c in (ctx.source.config.get("countries") or CA_CODES) if c.strip()}
        limit = int(ctx.source.config.get("limit") or 100)
        resp = await ctx.http.get(f"{SITE}/api/recent/{limit}", headers={"Accept": "application/json"})
        data = resp.json()
        if not isinstance(data, list):
            raise ConnectorError(f"Kutilmagan javob: {str(data)[:200]}", http_status=resp.status_code)
        items: list[RawItem] = []
        for v in data:
            if not isinstance(v, dict) or v.get("private"):
                continue
            title = (v.get("post_title") or "").strip()
            if not title:
                continue
            desc = v.get("description") or ""
            domain = extract_domain(title)
            tld = domain.rsplit(".", 1)[-1].upper() if domain else ""
            country = (v.get("country") or "").strip().upper()
            if not country and tld in codes:
                country = tld
            if not country:
                found = [c for c in detect_countries(title, desc) if c in codes]
                country = found[0] if found else ""
            if country not in codes:
                continue
            group = v.get("group_name") or "?"
            items.append(victim_item(
                victim=title, group=group, country=country, domain=domain, activity="",
                description=desc[:400], discovered=_parse_iso((v.get("discovered") or "").replace(" ", "T")),
                link=post_link(v.get("link"), group), source="ransomlook",
            ))
        return FetchResult(items, resp.status_code)
