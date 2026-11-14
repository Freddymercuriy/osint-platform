"""Testlar uchun yordamchilar: tarmoqsiz HTTP (httpx.MockTransport), soxta DNS, manba yaratish."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import httpx

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def rss(items: list[tuple[str, str, datetime | None]], title: str = "Test feed") -> bytes:
    """(sarlavha, havola, sana) → RSS 2.0."""
    parts = [f'<?xml version="1.0"?><rss version="2.0"><channel><title>{title}</title>']
    for t, link, when in items:
        date = f"<pubDate>{format_datetime(when)}</pubDate>" if when else ""
        parts.append(f"<item><title>{t}</title><link>{link}</link><description>{t}</description>{date}</item>")
    parts.append("</channel></rss>")
    return "".join(parts).encode()


def ago(**kw) -> datetime:
    return datetime.now(UTC) - timedelta(**kw)


def use_transport(monkeypatch, handler: Callable[[httpx.Request], httpx.Response]) -> list[httpx.Request]:
    """Scheduler HTTP so'rovlarini handler'ga yo'naltiradi; so'rovlar ro'yxatini qaytaradi."""
    from app.services.connectors import http
    from app.services.events import scheduler

    seen: list[httpx.Request] = []

    def _h(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(scheduler, "HTTP_TRANSPORT", httpx.MockTransport(_h))
    monkeypatch.setattr(scheduler.state, "_http", None)
    monkeypatch.setattr(http, "PAUSE_RANGE", (0.0, 0.0))
    monkeypatch.setattr(http, "RESOLVER", lambda host: ["127.0.0.1"] if host.startswith("internal") else ["93.184.216.34"])
    http.reset_gates()
    return seen
