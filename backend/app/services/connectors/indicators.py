"""Indikator (IOC) ulagichlari uchun umumiy yordamchilar: defang, xavfsiz URL, TLD → davlat, mintaqa tekshiruvi.

Indikatorlar faqat metadata: zararli URL'ga hech qachon so'rov yuborilmaydi; query string / fragment / userinfo
(ularda qurbonlarning email'lari bo'lishi mumkin) saqlanmaydi.
"""

from __future__ import annotations

import ipaddress
import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

CA_TLDS = {"uz": "UZ", "kz": "KZ", "kg": "KG", "tj": "TJ", "tm": "TM"}
_MAX_URL = 300


def host_of(value: str) -> str:
    """URL yoki 'host[:port]' dan kichik harfli xostni oladi (userinfo, port, oxirgi nuqtasiz)."""
    value = (value or "").strip()
    try:
        parts = urlsplit(value if "://" in value else f"//{value}")
        host = parts.hostname or ""
    except ValueError:
        return ""
    return host.lower().rstrip(".")


def is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def tld_country(host: str) -> str | None:
    """Xost milliy domen (.uz .kz .kg .tj .tm) ostida bo'lsa ISO-2 kodi."""
    host = (host or "").lower().rstrip(".")
    if not host or is_ip(host) or "." not in host:
        return None
    return CA_TLDS.get(host.rsplit(".", 1)[-1])


def safe_url(url: str) -> str | None:
    """Query string, fragment va userinfo olib tashlangan URL (faqat http/https). Path'dagi '@' li bo'laklar (email) tashlanadi."""
    try:
        parts = urlsplit((url or "").strip())
        host = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not host:
        return None
    host = host.lower().rstrip(".")
    if ":" in host:  # IPv6
        host = f"[{host}]"
    netloc = host + (f":{port}" if port else "")
    segments = [s for s in parts.path.split("/") if "@" not in s and "%40" not in s.lower()]
    path = "/".join(segments)
    if not path.startswith("/"):
        path = "/" + path
    return f"{parts.scheme.lower()}://{netloc}{path}"[:_MAX_URL]


def defang(value: str) -> str:
    """hxxp://example[.]uz/path — bosib ochib bo'lmaydigan ko'rinish."""
    out = re.sub(r"^http", "hxxp", value, flags=re.I)
    return out.replace(".", "[.]")


def parse_abusech_ts(value: str | None) -> datetime | None:
    """'2019-08-10 09:02:05 UTC' → tz-aware UTC."""
    if not value:
        return None
    try:
        return datetime.strptime(value.replace("UTC", "").strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return None
