"""ransomware.live — ransomware qurbonlari (davlat kodi bo'yicha).

config: {"countries": ["UZ", "KZ", "KG", "TJ", "TM"]}
Hozir: ochiq legacy `/v2/recentvictims` (oxirgi ~100 qurbon, ~1 so'rov/daqiqa, faqat shaxsiy foydalanish).
PRO API (kalit bilan) — Bosqich 3. `.onion` havolalar berilmaydi.
"""

from __future__ import annotations

import re

from app.services.connectors.base import Connector, ConnectorError, FetchContext, FetchResult, RawItem, register
from app.services.events.filters import _clean, _parse_iso

CA_CODES = ("UZ", "KZ", "KG", "TJ", "TM")
V2_RECENT = "https://api.ransomware.live/v2/recentvictims"


def victim_key(victim: str, domain: str = "") -> str:
    """Manbalararo bir xil qurbon: domen (bo'lsa) yoki nomning normallashtirilgan ko'rinishi."""
    d = (domain or "").lower().strip().removeprefix("http://").removeprefix("https://").removeprefix("www.")
    d = d.split("/")[0]
    if d and "." in d:
        return f"victim:{d}"
    name = re.sub(r"[^\w]+", "", (victim or "").lower())
    return f"victim:{name}"


def victim_item(*, victim: str, group: str, country: str, domain: str, activity: str, description: str,
                discovered, link: str, source: str) -> RawItem:
    title = f"[{group}] {victim} ({country})" + (f" — {activity}" if activity else "")
    return RawItem(
        title=title, url=link, summary=_clean(description or ""), published=discovered,
        category="ransomware", channel="api", countries=[country] if country else [],
        actor=(group or None) and str(group)[:128], sector=None,
        extra={"victim": victim, "group": group, "domain": domain or None, "activity": activity or None,
               "template": "ransomware_victim"},
        dedup_key=victim_key(victim, domain),
        lang="en",
    )


def public_link(url: str, group: str) -> str:
    if url.startswith("https://www.ransomware.live/") and ".onion" not in url:
        return url
    return f"https://www.ransomware.live/group/{str(group).lower()}"


@register
class RansomwareLiveConnector(Connector):
    kind = "ransomware_live"
    title = "ransomware.live (legacy v2)"
    config_fields = ("countries",)

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        codes = {c.strip().upper() for c in (ctx.source.config.get("countries") or CA_CODES) if c.strip()}
        domains = tuple(f".{c.lower()}" for c in codes)
        resp = await ctx.http.get(V2_RECENT)
        data = resp.json()
        if not isinstance(data, list):  # rate-limit javobi ({"message": ...})
            raise ConnectorError(f"Kutilmagan javob: {str(data)[:200]}", http_status=resp.status_code)
        items: list[RawItem] = []
        for v in data:
            country = (v.get("country") or "").strip().upper()
            domain = (v.get("domain") or "").strip().lower().rstrip("/")
            # Davlat maydoni bo'sh bo'lsa — milliy domen bo'yicha (masalan example.kz)
            if country not in codes and not (not country and domain.endswith(domains)):
                continue
            if not country:
                country = domain.rsplit(".", 1)[-1].upper()
            group = v.get("group") or v.get("group_name") or "?"
            activity = v.get("activity") or ""
            if activity.lower() in ("not found", "unknown"):
                activity = ""
            items.append(victim_item(
                victim=(v.get("victim") or v.get("post_title") or "Noma'lum").strip(), group=group,
                country=country, domain=domain, activity=activity, description=v.get("description") or "",
                discovered=_parse_iso(v.get("discovered") or v.get("attackdate")),
                link=public_link(v.get("url") or "", group), source="ransomware.live",
            ))
        return FetchResult(items, resp.status_code)
