"""Bosqich 2: manbalar admin API — ruxsatlar, CRUD, dry-run, hozir yig'ish, tarix, eksport/import, SSRF."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import func, select

from app.models import EventRecord, Source, SourceRun
from tests.helpers import ago, rss, use_transport

ADMIN_ROUTES = [
    ("get", "/api/admin/connectors"),
    ("get", "/api/admin/sources"),
    ("post", "/api/admin/sources"),
    ("get", "/api/admin/sources/export"),
    ("post", "/api/admin/sources/import"),
    ("post", "/api/admin/sources/test"),
    ("get", "/api/admin/sources/1"),
    ("patch", "/api/admin/sources/1"),
    ("delete", "/api/admin/sources/1"),
    ("post", "/api/admin/sources/1/enable"),
    ("post", "/api/admin/sources/1/disable"),
    ("post", "/api/admin/sources/1/test"),
    ("post", "/api/admin/sources/1/run"),
    ("get", "/api/admin/sources/1/runs"),
    ("get", "/api/admin/collector"),
]


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
async def test_admin_routes_require_admin(client, analyst_headers, method, path):
    kw = {"json": {}} if method in ("post", "patch") else {}
    assert (await client.request(method.upper(), path, **kw)).status_code == 401
    assert (await client.request(method.upper(), path, headers=analyst_headers, **kw)).status_code == 403


NEW = {"name": "My feed", "kind": "rss", "config": {"url": "https://feed.example/rss"}, "lang": "ru",
       "cyber_filter": True, "interval_seconds": 1200}


async def test_create_list_update_delete(client, admin_headers, db):
    r = await client.post("/api/admin/sources", json=NEW, headers=admin_headers)
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert r.json()["status"] == "never_run" and r.json()["next_run_at"] is not None
    assert (await client.post("/api/admin/sources", json=NEW, headers=admin_headers)).status_code == 409

    lst = (await client.get("/api/admin/sources?kind=rss&enabled=true", headers=admin_headers)).json()
    assert any(s["name"] == "My feed" for s in lst) and all(s["kind"] == "rss" for s in lst)

    r = await client.patch(f"/api/admin/sources/{sid}", json={"category": "phishing", "interval_seconds": 3600},
                           headers=admin_headers)
    assert r.status_code == 200 and r.json()["category"] == "phishing" and r.json()["interval_seconds"] == 3600
    assert (await client.patch(f"/api/admin/sources/{sid}", json={"category": "nope"},
                               headers=admin_headers)).status_code == 422
    assert (await client.patch(f"/api/admin/sources/{sid}", json={"interval_seconds": 10},
                               headers=admin_headers)).status_code == 422

    r = await client.post(f"/api/admin/sources/{sid}/disable", headers=admin_headers)
    assert r.json()["enabled"] is False and r.json()["status"] == "disabled" and r.json()["next_run_at"] is None
    r = await client.post(f"/api/admin/sources/{sid}/enable", headers=admin_headers)
    assert r.json()["enabled"] is True and r.json()["status"] == "never_run" and r.json()["next_run_at"]

    # o'chirilganda hodisalar qoladi (manba nomi bilan)
    db.add(EventRecord(uid="k1", source="My feed", source_id=sid, category="news", title="t",
                       url="https://feed.example/1", summary="", lang="ru"))
    await db.commit()
    assert (await client.delete(f"/api/admin/sources/{sid}", headers=admin_headers)).status_code == 204
    ev = await db.scalar(select(EventRecord).where(EventRecord.uid == "k1"))
    await db.refresh(ev)
    assert ev.source == "My feed" and ev.source_id is None
    assert (await client.get(f"/api/admin/sources/{sid}", headers=admin_headers)).status_code == 404


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/rss", "http://10.0.0.5/feed", "http://169.254.169.254/latest/meta-data",
    "http://[::1]/x", "javascript:alert(1)", "file:///etc/passwd",
])
async def test_create_refuses_internal_urls(client, admin_headers, url):
    r = await client.post("/api/admin/sources", json={**NEW, "config": {"url": url}}, headers=admin_headers)
    assert r.status_code == 422, r.text


async def test_create_refuses_hostname_resolving_to_private(client, admin_headers, monkeypatch):
    use_transport(monkeypatch, lambda req: httpx.Response(200))
    r = await client.post("/api/admin/sources", json={**NEW, "config": {"url": "https://internal.corp/rss"}},
                          headers=admin_headers)
    assert r.status_code == 422 and "Ichki" in r.text


async def test_api_key_env_must_be_a_key_name(client, admin_headers):
    for bad in ("SECRET_KEY", "DATABASE_URL", "TG_API_HASH", "lower_key", "PATH"):
        r = await client.post("/api/admin/sources", json={**NEW, "api_key_env": bad}, headers=admin_headers)
        assert r.status_code == 422, bad
    r = await client.post("/api/admin/sources", json={**NEW, "api_key_env": "OTX_API_KEY"}, headers=admin_headers)
    assert r.status_code == 201 and r.json()["key_configured"] is False


async def test_dry_run_stores_nothing(client, admin_headers, db, monkeypatch):
    use_transport(monkeypatch, lambda req: httpx.Response(200, headers={"ETag": '"e1"'}, content=rss([
        ("Хакеры взломали сайт в Ташкенте", "https://feed.example/1", ago(hours=1)),
        ("Погода в Ташкенте", "https://feed.example/2", ago(hours=1)),
        ("Утечка данных клиентов банка", "javascript:void(0)", ago(hours=1)),
    ])))
    created = (await client.post("/api/admin/sources", json=NEW, headers=admin_headers)).json()
    r = await client.post(f"/api/admin/sources/{created['id']}/test", headers=admin_headers)
    body = r.json()
    assert r.status_code == 200 and body["ok"] and body["http_status"] == 200
    assert body["items"] == 3 and body["passed"] == 1
    assert body["samples"][0]["title"].startswith("Хакеры") and body["samples"][0]["matched_keywords"]
    assert await db.scalar(select(func.count(EventRecord.id))) == 0
    assert await db.scalar(select(func.count(SourceRun.id))) == 0
    s = await db.get(Source, created["id"])
    await db.refresh(s)
    assert s.etag is None and s.last_check_at is None and not s.baseline_done

    # saqlanmagan qoralama ham sinaladi
    r = await client.post("/api/admin/sources/test", json=NEW, headers=admin_headers)
    assert r.json()["passed"] == 1


async def test_run_now_and_history(client, admin_headers, monkeypatch):
    use_transport(monkeypatch, lambda req: httpx.Response(200, content=rss([
        ("Хакеры взломали сайт в Ташкенте", "https://feed.example/1", ago(hours=1))])))
    sid = (await client.post("/api/admin/sources", json=NEW, headers=admin_headers)).json()["id"]
    r = await client.post(f"/api/admin/sources/{sid}/run", headers=admin_headers)
    assert r.status_code == 200 and r.json()["ok"] and r.json()["new"] == 1 and r.json()["status"] == "ok"
    runs = (await client.get(f"/api/admin/sources/{sid}/runs", headers=admin_headers)).json()
    assert len(runs) == 1 and runs[0]["manual"] and runs[0]["outcome"] == "ok" and runs[0]["new_items"] == 1
    one = (await client.get(f"/api/admin/sources/{sid}", headers=admin_headers)).json()
    assert one["items_24h"] == 1 and one["uptime_7d"] == 1.0 and one["baseline_done"]


async def test_export_import_roundtrip(client, admin_headers):
    exp = (await client.get("/api/admin/sources/export", headers=admin_headers)).json()
    assert exp["format"] == "osint-sources" and len(exp["sources"]) == 80
    assert all("status" not in s and "etag" not in s for s in exp["sources"])
    item = dict(exp["sources"][0])
    item["interval_seconds"] = 4321
    new = {**NEW, "name": "Imported"}
    r = await client.post("/api/admin/sources/import", json={"sources": [item, new]}, headers=admin_headers)
    assert r.json() == {"created": 1, "updated": 1}
    lst = {s["name"]: s for s in (await client.get("/api/admin/sources", headers=admin_headers)).json()}
    assert lst[item["name"]]["interval_seconds"] == 4321 and "Imported" in lst


async def test_collector_status(client, admin_headers):
    r = await client.get("/api/admin/collector", headers=admin_headers)
    body = r.json()
    assert r.status_code == 200 and body["sources_total"] == 80
    assert body["by_status"]["auth_missing"] == 5 and body["by_status"]["blocked"] == 2


async def test_telegram_flood_wait_maps_to_rate_limited(monkeypatch):
    from telethon import errors

    from app.services import telegram_user as tg
    from app.services.connectors.base import FetchContext, RateLimited, SourceView
    from app.services.connectors.telegram_user import TelegramUserConnector

    async def boom():
        raise errors.FloodWaitError(request=None, capture=42)

    monkeypatch.setattr(tg, "is_configured", lambda: True)
    monkeypatch.setattr(tg, "fetch_messages", boom)
    view = SourceView(id=1, name="TG", kind="telegram_user", config={}, lang="uz", scope="regional",
                      region_filter=False, cyber_filter=False, api_key_env=None, etag=None, last_modified=None,
                      state={}, backfill_days=14)
    with pytest.raises(RateLimited) as exc:
        await TelegramUserConnector().fetch(FetchContext(source=view, http=None))
    assert exc.value.retry_after == 42


async def test_shorter_interval_pulls_next_run_earlier_but_respects_retry_after(client, admin_headers, db):
    """30 daq → 60 s: eski reja kutilmaydi; sayt so'ragan kutish (Retry-After) esa qisqartirilmaydi."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    s = Source(name="Slow", kind="rss", config={"url": "https://feed.example/rss"}, interval_seconds=1800,
               jitter_pct=0, enabled=True, status="ok", next_run_at=now + timedelta(minutes=29))
    blocked = Source(name="Limited", kind="rss", config={"url": "https://feed.example/l"}, interval_seconds=1800,
                     jitter_pct=0, enabled=True, status="blocked", last_outcome="rate_limited",
                     retry_after_seconds=600, last_check_at=now, next_run_at=now + timedelta(minutes=29))
    db.add_all([s, blocked])
    await db.commit()

    r = await client.patch(f"/api/admin/sources/{s.id}", json={"interval_seconds": 60}, headers=admin_headers)
    assert r.status_code == 200
    nxt = datetime.fromisoformat(r.json()["next_run_at"])
    assert now + timedelta(seconds=55) <= nxt <= datetime.now(UTC) + timedelta(seconds=61)

    r = await client.patch(f"/api/admin/sources/{blocked.id}", json={"interval_seconds": 60}, headers=admin_headers)
    nxt = datetime.fromisoformat(r.json()["next_run_at"])
    assert now + timedelta(seconds=599) <= nxt <= now + timedelta(seconds=601)  # Retry-After 600 s hurmat qilindi

    # Oraliq uzaysa — mavjud reja o'zgarmaydi
    before = datetime.fromisoformat((await client.get(f"/api/admin/sources/{s.id}", headers=admin_headers)).json()["next_run_at"])
    r = await client.patch(f"/api/admin/sources/{s.id}", json={"interval_seconds": 3600}, headers=admin_headers)
    assert datetime.fromisoformat(r.json()["next_run_at"]) == before
