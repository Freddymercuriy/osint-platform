"""Bosqich 7: foydalanuvchilar admin API, uzoq ishlamayotgan manba ogohlantirishi, Events fasetlari."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.models import AdminAlert, EventRecord, Source, User
from app.services.events import scheduler
from tests.helpers import ago, rss, use_transport


@pytest.mark.parametrize("method,path", [("get", "/api/admin/users"), ("patch", "/api/admin/users/1")])
async def test_users_routes_admin_only(client, analyst_headers, method, path):
    kw = {"json": {}} if method == "patch" else {}
    assert (await client.request(method.upper(), path, headers=analyst_headers, **kw)).status_code == 403


async def test_users_list_role_and_last_admin(client, make_user, db):
    admin, ah = await make_user("boss@example.com", role="admin")
    other, oh = await make_user("user@example.com", role="analyst")
    rows = (await client.get("/api/admin/users", headers=ah)).json()
    assert [r["email"] for r in rows] == ["boss@example.com", "user@example.com"]
    assert {"role", "is_active", "locale", "searches"} <= set(rows[0])

    # oxirgi faol adminni pasaytirib / o'chirib bo'lmaydi
    r = await client.patch(f"/api/admin/users/{admin.id}", json={"role": "analyst"}, headers=ah)
    assert r.status_code == 409 and r.json()["code"] == "last_admin"
    r = await client.patch(f"/api/admin/users/{admin.id}", json={"is_active": False}, headers=ah)
    assert r.status_code == 409

    r = await client.patch(f"/api/admin/users/{other.id}", json={"role": "admin"}, headers=ah)
    assert r.json()["role"] == "admin"
    r = await client.patch(f"/api/admin/users/{admin.id}", json={"role": "analyst"}, headers=ah)
    assert r.status_code == 200 and r.json()["role"] == "analyst"

    # birinchi admin endi analyst — admin route'lari unga yopiq; yangi admin o'zini o'chira olmaydi (oxirgi admin)
    assert (await client.get("/api/admin/users", headers=ah)).status_code == 403
    r = await client.patch(f"/api/admin/users/{other.id}", json={"is_active": False}, headers=oh)
    assert r.status_code == 409
    assert (await client.patch("/api/admin/users/9999", json={"role": "admin"}, headers=oh)).status_code == 404


async def test_down_source_alert_raised_and_resolved(client, db, monkeypatch, make_user):
    _, admin_h = await make_user("boss@example.com", role="admin")
    _, analyst_h = await make_user("a@example.com", role="analyst")
    s = Source(name="Flaky", kind="rss", config={"url": "https://flaky.example/rss"}, interval_seconds=600,
               status="down", consecutive_failures=5, down_since=datetime.now(UTC) - timedelta(hours=4),
               last_error="HTTP 500")
    fresh = Source(name="Fresh down", kind="rss", config={"url": "https://f2.example/rss"}, interval_seconds=600,
                   status="down", down_since=datetime.now(UTC) - timedelta(minutes=30))
    db.add_all([s, fresh])
    await db.commit()

    assert await scheduler.raise_down_alerts(db) == 1
    assert await scheduler.raise_down_alerts(db) == 0  # takror yaratilmaydi
    body = (await client.get("/api/notifications", headers=admin_h)).json()
    assert len(body["system"]) == 1 and body["system"][0]["data"]["source"] == "Flaky"
    assert body["system"][0]["kind"] == "source_down" and body["unread"] >= 1
    assert (await client.get("/api/notifications", headers=analyst_h)).json()["system"] == []

    use_transport(monkeypatch, lambda req: httpx.Response(200, content=rss([("x", "https://flaky.example/1", ago(hours=1))])))
    await scheduler.run_source(s.id)
    alert = await db.scalar(select(AdminAlert).where(AdminAlert.source_id == s.id))
    await db.refresh(alert)
    assert alert.resolved_at is not None
    assert (await client.get("/api/notifications", headers=admin_h)).json()["system"] == []


async def test_event_facets(client, analyst_headers, db):
    src = await db.scalar(select(Source).where(Source.name == "UZCERT"))
    db.add_all([
        EventRecord(uid="a", source="UZCERT", source_id=src.id, category="vulnerability", title="t1",
                    url="https://x.example/1", summary="", lang="uz", countries=["UZ"], channel="news"),
        EventRecord(uid="b", source="UZCERT", source_id=src.id, category="vulnerability", title="t2",
                    url="https://x.example/2", summary="", lang="ru", countries=["UZ", "KZ"], channel="news",
                    severity="high"),
    ])
    await db.commit()
    f = (await client.get("/api/events/facets", headers=analyst_headers)).json()
    assert f["sources"] == [{"value": str(src.id), "label": "UZCERT", "count": 2}]
    assert {c["value"]: c["count"] for c in f["countries"]} == {"UZ": 2, "KZ": 1}
    assert {c["value"] for c in f["source_langs"]} == {"uz", "ru"}
    assert {c["value"]: c["count"] for c in f["severities"]} == {"info": 1, "high": 1}
