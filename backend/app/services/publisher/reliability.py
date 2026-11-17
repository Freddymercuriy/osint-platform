"""Manba ishonchliligining boshlang'ich qiymati (migratsiya 0018 dagi qoida bilan bir xil). Admin o'zgartira oladi."""

from __future__ import annotations

import re

from app.core.config import settings

TRACKER_KINDS = frozenset({"ransomware_live", "ransomware_live_pro", "ransomlook", "hibp_breaches", "threatfox",
                           "urlhaus", "openphish", "otx_pulses", "cloudflare_radar"})
OFFICIAL_KINDS = frozenset({"cisa_kev", "nvd_cves"})
_OFFICIAL_NAME = re.compile(r"(cert\b|sts\.kz|kcokb)", re.IGNORECASE)  # UZCERT, KZ-CERT, CERT.TJ
UNDERGROUND_CATEGORIES = frozenset({"leak", "darkweb-sale"})


def default_reliability(kind: str, name: str = "", *, category: str | None = None, chat: str | None = None) -> str:
    if kind in OFFICIAL_KINDS or (kind in ("rss", "html_list") and _OFFICIAL_NAME.search(name or "")):
        return "official"
    if kind in TRACKER_KINDS:
        return "tracker"
    if kind == "telegram_user":
        leak = {c.lower() for c in settings.tg_leak_chats_list}
        if (chat and chat.lstrip("@").lower() in leak) or category in UNDERGROUND_CATEGORIES:
            return "underground"
        return "community"
    return "media"
