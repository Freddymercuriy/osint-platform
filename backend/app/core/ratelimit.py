"""Oddiy rate limiting (jarayon xotirasida, sirpanuvchi oyna) — Redis kabi qo'shimcha xizmatsiz.

API bitta uvicorn jarayonida ishlaydi (Telethon sessiyasi va yig'uvchi tufayli), shuning uchun xotiradagi hisob yetarli.
Chegaradan oshsa: 429, `Retry-After` sarlavhasi va `code: too_many_requests`.

- login: IP bo'yicha va email bo'yicha (parol tanlashni sekinlatadi);
- tekshiruvlar (`/api/search/*`): foydalanuvchi bo'yicha;
- qo'lda yig'ish (`/api/events/refresh`, manbani "hozir yig'ish"): foydalanuvchi bo'yicha.
"""

from __future__ import annotations

import math
import time
from collections import deque

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


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check(name: str, key: str, limit: int, window: float) -> None:
    if not settings.rate_limit_enabled or limit <= 0:
        return
    retry = limiter.hit(f"{name}:{key}", limit, window)
    if retry is not None:
        seconds = math.ceil(retry)
        raise ApiError(429, "too_many_requests", headers={"Retry-After": str(seconds)}, seconds=seconds)
