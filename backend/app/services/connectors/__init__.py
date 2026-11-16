"""Manba ulagichlari. Har tur — bitta modul; import qilinganda `@register` bilan ro'yxatga tushadi."""

from app.services.connectors import (  # noqa: F401
    abusech,
    cisa_kev,
    cloudflare_radar,
    google_news,
    hibp,
    html_list,
    newsnow,
    nvd,
    openphish,
    otx,
    ransomlook,
    ransomware_live,
    ransomware_live_pro,
    rss,
    telegram_public,
    telegram_user,
)
from app.services.connectors.base import CONNECTORS, get_connector  # noqa: F401
