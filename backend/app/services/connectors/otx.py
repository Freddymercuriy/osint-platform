"""LevelBlue (ex-AlienVault) OTX — obuna qilingan pulse'lar, faqat Markaziy Osiyoni tilga olganlari.

Hujjat/SDK: https://github.com/AlienVault-OTX/OTX-Python-SDK (OTXv2.py: `GET /api/v1/pulses/subscribed`,
`limit`, `page`, `modified_since`, javobda `results` va `next` (to'liq URL)); sarlavha `X-OTX-API-KEY`.
Baza URL `https://otx.alienvault.com` hozir ham ishlaydi (kalitsiz — 403 JSON).
Faqat metadata: indikatorlar (IP/hash/domen) saqlanmaydi, faqat soni.

config: {"countries": [...], "limit": 50, "max_pages": 5}; state: {"modified_since": iso}
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.connectors.base import (
    AuthMissing, Connector, ConnectorError, FetchContext, FetchResult, RawItem, RateLimited, SourceBlocked, register,
)
from app.services.events.filters import _clean, _parse_iso
from app.services.events.geo import detect_countries

BASE = "https://otx.alienvault.com"
SUBSCRIBED = f"{BASE}/api/v1/pulses/subscribed"
CA_CODES = ("UZ", "KZ", "KG", "TJ", "TM")
SKIP_TLP = {"red", "amber"}
TAG_CATEGORIES = (("ransomware", "ransomware"), ("phishing", "phishing"), ("malware", "malware"))


def _names(values: Any, *keys: str) -> list[str]:
    """OTX ba'zan satr, ba'zan {"id","display_name"} obyektlar qaytaradi."""
    out: list[str] = []
    for v in values or []:
        if isinstance(v, dict):
            v = next((v.get(k) for k in keys if v.get(k)), None)
        if v:
            out.append(str(v)[:128])
    return out


def pulse_countries(pulse: dict, wanted: set[str]) -> list[str]:
    """targeted_countries (nom yoki ISO kod) + nom/tavsif/teglar matni."""
    found: set[str] = set()
    targeted = [str(c).strip() for c in (pulse.get("targeted_countries") or []) if c]
    for c in targeted:
        if c.upper() in wanted:
            found.add(c.upper())
    found.update(detect_countries(*targeted))
    found.update(detect_countries(pulse.get("name"), pulse.get("description"), " ".join(_names(pulse.get("tags"), "name"))))
    return [c for c in CA_CODES if c in found and c in wanted]


def _category(tags: list[str]) -> str | None:
    low = {t.lower() for t in tags}
    for needle, slug in TAG_CATEGORIES:
        if needle in low:
            return slug
    return None


@register
class OtxPulsesConnector(Connector):
    kind = "otx_pulses"
    title = "LevelBlue OTX pulses"
    key = "required"
    default_key_env = "OTX_API_KEY"
    config_fields = ("countries",)

    async def _get(self, ctx: FetchContext, url: str, params: dict | None):
        try:
            return await ctx.http.get(url, headers={"X-OTX-API-KEY": ctx.api_key or ""}, params=params)
        except RateLimited:
            raise
        except SourceBlocked as exc:
            if exc.http_status == 403:  # OTX: kalit yo'q/noto'g'ri → 403
                raise AuthMissing("OTX kaliti yo'q yoki rad etildi (HTTP 403)", http_status=403) from exc
            raise

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        if not ctx.api_key:
            raise AuthMissing("OTX_API_KEY sozlanmagan")
        cfg = ctx.source.config or {}
        wanted = {c.strip().upper() for c in (cfg.get("countries") or CA_CODES) if c and c.strip()}
        limit = int(cfg.get("limit") or 50)
        max_pages = int(cfg.get("max_pages") or 5)

        since = None if ctx.dry_run else (ctx.source.state or {}).get("modified_since")
        if not since:
            since = (datetime.now(UTC) - timedelta(days=ctx.source.backfill_days or 14)).strftime("%Y-%m-%dT%H:%M:%S")

        items: list[RawItem] = []
        seen_ids: set[str] = set()
        mods: list[str] = []
        url: str | None = SUBSCRIBED
        params: dict | None = {"limit": limit, "page": 1, "modified_since": since}
        status = None
        pages = 0
        drained = False
        while url and pages < max_pages:
            resp = await self._get(ctx, url, params)
            status = resp.status_code
            pages += 1
            data = resp.json()
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                raise ConnectorError("OTX: kutilmagan javob shakli", http_status=status)
            for pulse in data["results"]:
                if not isinstance(pulse, dict):
                    continue
                if pulse.get("modified"):
                    mods.append(str(pulse["modified"]))
                item = self._item(pulse, wanted)
                if item and item.extra["otx_id"] not in seen_ids:
                    seen_ids.add(item.extra["otx_id"])
                    items.append(item)
            url, params = data.get("next"), None  # `next` — to'liq URL (parametrlar bilan)
            if not url:
                drained = True

        state = None
        if not ctx.dry_run and mods:
            ordered_asc = len(mods) < 2 or mods[0] <= mods[-1]
            # Sahifa chegarasiga yetsak va tartib kamayuvchi bo'lsa kursor siljitilmaydi (o'tkazib yubormaslik uchun)
            if drained or ordered_asc:
                state = {"modified_since": max(mods)}
        note = None if drained else f"{max_pages} sahifa chegarasiga yetildi"
        return FetchResult(items, status, state=state, note=note)

    def _item(self, pulse: dict, wanted: set[str]) -> RawItem | None:
        pid = pulse.get("id")
        if not pid or (pulse.get("tlp") or "").lower() in SKIP_TLP:
            return None
        countries = pulse_countries(pulse, wanted)
        if not countries:
            return None
        tags = _names(pulse.get("tags"), "name")
        adversary = (pulse.get("adversary") or "").strip() or None
        indicators = pulse.get("indicators")
        count = pulse.get("indicator_count")
        if count is None:
            count = len(indicators) if isinstance(indicators, list) else None
        return RawItem(
            title=str(pulse.get("name") or "OTX pulse").strip()[:300],
            url=f"https://otx.alienvault.com/pulse/{pid}",
            summary=_clean(pulse.get("description") or "")[:600],
            published=_parse_iso(pulse.get("modified") or pulse.get("created")),
            lang="en", category=_category(tags), channel="api", countries=countries,
            actor=adversary[:128] if adversary else None,
            extra={"otx_id": str(pid), "tags": tags[:20],
                   "malware_families": _names(pulse.get("malware_families"), "display_name", "id", "name")[:20],
                   "attack_ids": _names(pulse.get("attack_ids"), "id", "display_name")[:30],
                   "indicator_count": count, "tlp": (pulse.get("tlp") or None)},
        )
