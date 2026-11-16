"""Oddiy rate limiting (jarayon xotirasida, sirpanuvchi oyna) — Redis kabi qo'shimcha xizmatsiz.

API bitta uvicorn jarayonida ishlaydi (Telethon sessiyasi va yig'uvchi tufayli), shuning uchun xotiradagi hisob yetarli.
Chegaradan oshsa: 429, `Retry-After` sarlavhasi va `code: too_many_requests`.

- login: IP bo'yicha va email bo'yicha (parol tanlashni sekinlatadi);
- tekshiruvlar (`/api/search/*`): foydalanuvchi bo'yicha;
- qo'lda yig'ish (`/api/events/refresh`, manbani "hozir yig'ish"): foydalanuvchi bo'yicha.

Proxy ortida: `TRUSTED_PROXIES` dagi manzildan kelgan so'rovda mijoz IP'si `X-Forwarded-For` dan olinadi.
"""

from __future__ import annotations

import ipaddress
import math
import time
from collections import deque
from functools import lru_cache

from fastapi import Request

from app.core.config import settings
from app.core.errors import ApiError


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str, limit: int, window: float, now: float | None = None) -> float | None:
        """Urinishni qayd etadi. Chegaradan oshsa — necha soniyadan keyin mumkinligi, aks holda None."""
        now = time.monotonic() if now is None else now
        q = self._hits.setdefault(key, deque())
        while q and q[0] <= now - window:
            q.popleft()
        if len(q) >= limit:
            return max(1.0, q[0] + window - now)
        q.append(now)
        if len(self._hits) > 50_000:  # xotira cheklovi: eski bo'sh kalitlarni tozalash
            for k in [k for k, v in self._hits.items() if not v][:10_000]:
                self._hits.pop(k, None)
        return None

    def clear(self) -> None:
        self._hits.clear()


limiter = SlidingWindow()


IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


@lru_cache(maxsize=8)
def _trusted_networks(raw: str) -> tuple[IPNetwork, ...]:
    nets = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            nets.append(ipaddress.ip_network(part, strict=False))  # sozlamada tekshirilgan
    return tuple(nets)


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    value = value.strip()
    if value.startswith("[") and "]" in value:  # [2001:db8::1]:443
        value = value[1:value.index("]")]
    elif value.count(":") == 1:  # 203.0.113.5:443
        value = value.split(":", 1)[0]
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _is_trusted(ip, nets: tuple[IPNetwork, ...]) -> bool:
    return ip is not None and any(ip in n for n in nets)


def client_ip(request: Request) -> str:
    """Mijoz IP'si. `X-Forwarded-For` faqat ishonchli proxy'dan kelgan so'rovda o'qiladi (aks holda soxtalashtirish
    mumkin): zanjir o'ngdan ko'riladi, ishonchli proxy'lar o'tkazib yuboriladi, birinchi qolgan manzil — mijoz."""
    peer = request.client.host if request.client else "unknown"
    nets = _trusted_networks(settings.trusted_proxies)
    if not nets or not _is_trusted(_parse_ip(peer), nets):
        return peer
    hops = [h for v in request.headers.getlist("x-forwarded-for") for h in v.split(",") if h.strip()]
    for hop in reversed(hops):
        ip = _parse_ip(hop)
        if ip is None:
            return peer  # buzilgan zanjir — proxy manzili bo'yicha hisoblaymiz
        if not _is_trusted(ip, nets):
            return str(ip)
    return str(_parse_ip(hops[0])) if hops else peer  # butun zanjir ishonchli — eng chapdagisi mijoz


def check(name: str, key: str, limit: int, window: float) -> None:
    if not settings.rate_limit_enabled or limit <= 0:
        return
    retry = limiter.hit(f"{name}:{key}", limit, window)
    if retry is not None:
        seconds = math.ceil(retry)
        raise ApiError(429, "too_many_requests", headers={"Retry-After": str(seconds)}, seconds=seconds)
