"""Bosqich 9: rate limiting (login, qo'lda yig'ish) va admin route'lari to'liq qamrovi."""

from __future__ import annotations

import pytest

from app.core import ratelimit
from app.core.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def _fresh_limiter():
    ratelimit.limiter.clear()
    yield
    ratelimit.limiter.clear()


def test_sliding_window():
    w = ratelimit.SlidingWindow()
    assert all(w.hit("k", 3, 60, now=float(i)) is None for i in range(3))
    retry = w.hit("k", 3, 60, now=10.0)
    assert retry == pytest.approx(50.0)
    assert w.hit("k", 3, 60, now=61.0) is None  # birinchi urinish oynadan chiqdi


async def test_login_rate_limited_by_email(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "login_rate_email", 3)
    await make_user("victim@example.com", password="right-password")
    for _ in range(3):
        r = await client.post("/api/auth/login", data={"username": "victim@example.com", "password": "wrong-pass"})
        assert r.status_code == 401
    r = await client.post("/api/auth/login", data={"username": "victim@example.com", "password": "right-password"},
                          headers={"Accept-Language": "en"})
    assert r.status_code == 429 and r.json()["code"] == "too_many_requests"
    assert int(r.headers["retry-after"]) > 0 and "Too many requests" in r.json()["detail"]
    # boshqa email — bloklanmagan
    r = await client.post("/api/auth/login", data={"username": "other@example.com", "password": "x"})
    assert r.status_code == 401


async def test_login_rate_limited_by_ip(client, monkeypatch):
    monkeypatch.setattr(settings, "login_rate_ip", 2)
    for i in range(2):
        await client.post("/api/auth/login", data={"username": f"u{i}@example.com", "password": "x"})
    r = await client.post("/api/auth/login", data={"username": "u9@example.com", "password": "x"})
    assert r.status_code == 429


async def test_refresh_rate_limited(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "refresh_rate", 1)
    monkeypatch.setattr(settings, "events_poll_enabled", False)
    from app.services.events import scheduler

    async def nothing(ids, manual=True, timeout=90):
        return []

    monkeypatch.setattr(scheduler, "run_many", nothing)
    assert (await client.post("/api/events/refresh", headers=admin_headers)).status_code == 200
    assert (await client.post("/api/events/refresh", headers=admin_headers)).status_code == 429


async def test_rate_limit_can_be_disabled(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "login_rate_email", 1)
    for _ in range(3):
        r = await client.post("/api/auth/login", data={"username": "z@example.com", "password": "x"})
        assert r.status_code == 401


def _admin_routes():
    out = []
    for r in app.routes:
        path = getattr(r, "path", "")
        if path.startswith("/api/admin") or path.startswith("/api/telegram") or path == "/api/events/refresh" or (
            path == "/api/events/{event_id}"
        ):
            for m in sorted(getattr(r, "methods", []) - {"HEAD", "OPTIONS"}):
                out.append((m, path.replace("{source_id}", "1").replace("{category_id}", "1").replace(
                    "{user_id}", "1").replace("{event_id}", "1")))
    return out


ADMIN_ROUTES = _admin_routes()


def test_admin_route_inventory_is_complete():
    # yangi admin route qo'shilsa ham pastdagi test uni avtomatik tekshiradi
    assert len(ADMIN_ROUTES) >= 30


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
async def test_every_admin_route_rejects_analyst(client, analyst_headers, method, path):
    kw = {"json": {}} if method in ("POST", "PATCH", "PUT") else {}
    r = await client.request(method, path, headers=analyst_headers, **kw)
    assert r.status_code == 403, (method, path, r.status_code)
    assert r.json()["code"] == "admin_only"
    assert (await client.request(method, path, **kw)).status_code == 401
