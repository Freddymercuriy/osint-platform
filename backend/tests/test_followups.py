"""v2 dan keyingi kichik ishlar: Events nisbiy davri (soat aniqligida), proxy ortida mijoz IP'si, tarix hisoblagichi."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from starlette.requests import Request

from app.core import ratelimit
from app.core.config import Settings, settings
from app.models import EventRecord


# ---------------------------------------------------------------- Events: range=24h|7d|30d|90d
async def test_events_range_is_hour_precise(client, analyst_headers, db):
    now = datetime.now(UTC)
    for uid, age in [("h23", timedelta(hours=23)), ("h25", timedelta(hours=25)),
                     ("d6", timedelta(days=6)), ("d8", timedelta(days=8)), ("d40", timedelta(days=40))]:
        db.add(EventRecord(uid=uid, url=f"https://x.example/{uid}", title=uid, summary="", category="leak",
                           severity="high", countries=["UZ"], channel="news", scope="regional", lang="en",
                           source="t", published=now - age))
    await db.commit()

    async def titles(qs: str) -> list[str]:
        r = await client.get(f"/api/events?{qs}", headers=analyst_headers)
        assert r.status_code == 200, r.text
        return sorted(i["title"] for i in r.json()["items"])

    # "24 soat" — aynan 24 soat (avval date_from=kecha bilan ~48 soat ko'rsatardi)
    assert await titles("range=24h") == ["h23"]
    assert await titles("range=7d") == ["d6", "h23", "h25"]
    assert await titles("range=30d") == ["d6", "d8", "h23", "h25"]
    assert len(await titles("range=90d")) == 5
    # aniq sana berilsa — u ustun (statistika bilan bir xil qoida)
    d = (now - timedelta(days=10)).date().isoformat()
    assert await titles(f"range=24h&date_from={d}") == ["d6", "d8", "h23", "h25"]
    r = await client.get("/api/events?range=1y", headers=analyst_headers)
    assert r.status_code == 422


# ---------------------------------------------------------------- mijoz IP'si (X-Forwarded-For)
def _request(peer: str, xff: list[str] | None = None) -> Request:
    headers = [(b"x-forwarded-for", v.encode()) for v in (xff or [])]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers, "client": (peer, 1234)})


@pytest.mark.parametrize("trusted,peer,xff,expected", [
    ("", "10.0.0.2", ["1.2.3.4"], "10.0.0.2"),  # sozlanmagan — sarlavha e'tiborsiz
    ("10.0.0.0/8", "198.51.100.7", ["1.2.3.4"], "198.51.100.7"),  # ishonchsiz manbadan — soxta bo'lishi mumkin
    ("10.0.0.0/8", "10.0.0.2", ["1.2.3.4"], "1.2.3.4"),
    ("10.0.0.0/8", "10.0.0.2", ["6.6.6.6, 1.2.3.4"], "1.2.3.4"),  # chapdagisi mijoz tomonidan soxtalashtirilgan
    ("10.0.0.0/8", "10.0.0.2", ["6.6.6.6, 1.2.3.4, 10.0.0.9"], "1.2.3.4"),  # ichki proxy'lar zanjiri
    ("10.0.0.0/8", "10.0.0.2", ["6.6.6.6", "1.2.3.4"], "1.2.3.4"),  # bir nechta sarlavha
    ("10.0.0.0/8", "10.0.0.2", ["1.2.3.4:5678"], "1.2.3.4"),
    ("10.0.0.0/8,2001:db8::/32", "2001:db8::1", ["[2001:db8:ffff::5]:443, 2a00:1450::1"], "2a00:1450::1"),
    ("10.0.0.0/8", "10.0.0.2", ["1.2.3.4, garbage"], "10.0.0.2"),  # buzilgan zanjir
    ("10.0.0.0/8", "10.0.0.2", [], "10.0.0.2"),
    ("10.0.0.0/8", "10.0.0.2", ["10.0.0.5"], "10.0.0.5"),  # butun zanjir ichki
])
def test_client_ip(monkeypatch, trusted, peer, xff, expected):
    monkeypatch.setattr(settings, "trusted_proxies", trusted)
    assert ratelimit.client_ip(_request(peer, xff)) == expected


def test_trusted_proxies_validated_at_startup():
    with pytest.raises(ValueError):
        Settings(trusted_proxies="10.0.0.0/8, not-an-ip")


async def test_login_limit_per_forwarded_client(client, monkeypatch):
    # ASGI test mijozi 127.0.0.1 dan keladi — uni proxy deb belgilaymiz
    monkeypatch.setattr(settings, "trusted_proxies", "127.0.0.1")
    monkeypatch.setattr(settings, "login_rate_ip", 2)

    async def login(ip: str) -> int:
        r = await client.post("/api/auth/login", data={"username": f"{ip}@example.com", "password": "x"},
                              headers={"X-Forwarded-For": ip})
        return r.status_code

    assert [await login("1.1.1.1") for _ in range(3)] == [401, 401, 429]
    assert await login("2.2.2.2") == 401  # boshqa mijoz proxy ortida ham alohida hisoblanadi


# ---------------------------------------------------------------- CORS_ALLOW_LAN
@pytest.mark.parametrize("origin,allowed", [
    ("http://localhost:3000", True), ("http://192.168.1.117:3000", True), ("http://10.0.0.5:3000", True),
    ("http://172.20.1.2:3000", True), ("http://100.67.104.58:3000", False), ("http://pc.local:3000", True),
    ("http://osint-pc:3000", True),
    ("http://evil.example:3000", False), ("http://192.168.1.117:4000", False), ("http://8.8.8.8:3000", False),
    ("http://172.32.0.1:3000", False), ("http://100.128.0.1:3000", False), ("http://192.168.1.117.evil.com:3000", False),
    ("http://a.b.local:3000", False), ("http://192.168.1.117:3000.evil.com", False),
])
def test_lan_origin_regex(origin, allowed):
    import re

    from app.core.config import LAN_ORIGIN_RE

    assert bool(re.fullmatch(LAN_ORIGIN_RE, origin)) is allowed
    assert Settings(cors_allow_lan=True).cors_origin_regex == LAN_ORIGIN_RE
    assert Settings(cors_allow_lan=False).cors_origin_regex is None
