"""Manba ulagichlari. Har tur — bitta modul; import qilinganda `@register` bilan ro'yxatga tushadi."""

from app.services.connectors import (  # noqa: F401
    google_news,
    ransomware_live,
    rss,
    telegram_public,
    telegram_user,
)
from app.services.connectors.base import CONNECTORS, get_connector  # noqa: F401
