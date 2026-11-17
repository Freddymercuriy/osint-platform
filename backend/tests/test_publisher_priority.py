"""Ustuvorlik: ball / band / sabablar, yozuvlar soni, kuzatuv ro'yxati (lotin, kirill, apostrof), qayta hisoblash,
admin API va Events band filtri."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import Category, EventRecord, PublisherSettings, Source, WatchlistEntry
from app.services.connectors.base import RawItem
from app.services.events import pipeline
from app.services.events.geo import detect_sector
from app.services.publisher import priority as pr
from app.services.publisher import scoring
from app.services.publisher.watchlist import compile_watchlist, event_texts, match

NOW = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)


def inp(**kw) -> pr.PriorityInput:
    base = dict(severity="high", countries=[], sector=None, scope="regional", reliability="media", source="Kun.uz",
                also_reported_by=[], published=NOW, first_seen=NOW)
    base.update(kw)
    return pr.PriorityInput(**base)


def codes(p: pr.Priority) -> dict[str, int]:
    return {r["code"]: r["points"] for r in p.reasons}


# ---------------------------------------------------------------- sof hisoblash
def test_starting_weights_and_bands():
    p = pr.compute(inp(severity="critical", countries=["UZ"], sector="finance"))
    assert (p.score, p.band) == (90, "critical")
    assert codes(p) == {"sev_critical": 50, "country_uz": 30, "sector": 10}
    p = pr.compute(inp(severity="high", countries=["KZ", "UZ"]))
    assert codes(p) == {"sev_high": 35, "country_uz": 30} and p.band == "high"  # UZ bo'lsa — boshqa CA qo'shilmaydi
    p = pr.compute(inp(severity="high", countries=["KZ"]))
    assert (p.score, p.band, codes(p)["country_ca"]) == (50, "medium", 15)
    assert [r.get("arg") for r in p.reasons if r["code"] == "country_ca"] == ["KZ"]
    assert pr.compute(inp(severity="medium")).band == "low"
    assert pr.compute(inp(severity="info", sector="education")).score == 0  # education — muhim sohalar ro'yxatida emas


def test_watchlist_official_sources_records_stale_underground():
    p = pr.compute(inp(severity="medium", watch_hits=[("brand", "Payme"), ("domain", "my.gov.uz"),
                                                      ("product", "Fortinet"), ("person", "X")]))
    assert codes(p) == {"sev_medium": 20, "watch_org": 40, "watch_product": 25, "watch_person": 30}  # har guruh bir marta
    assert p.score == 100 and p.band == "critical"  # 115 → 100 gacha
    p = pr.compute(inp(reliability="official", severity="high", countries=["UZ"]))
    assert codes(p)["official_source"] == 10 and p.score == 75
    # Google News nusxasi qayta sanalmaydi; 2 tadan ortiq qo'shimcha manba hisobga olinmaydi
    reps = [{"source": "Kun.uz (Google News)"}, {"source": "Daryo"}, {"source": "Gazeta.uz"}, {"source": "Spot"}]
    p = pr.compute(inp(also_reported_by=reps))
    assert codes(p)["multi_source"] == 10 and [r["arg"] for r in p.reasons if r["code"] == "multi_source"] == [4]
    p = pr.compute(inp(also_reported_by=[{"source": "Kun.uz (Google News)"}]))
    assert "multi_source" not in codes(p)
    assert codes(pr.compute(inp(records=8_300_000)))["records_1m"] == 10
    assert codes(pr.compute(inp(records=150_000)))["records_100k"] == 5
    assert "records_100k" not in codes(pr.compute(inp(records=99_999)))
    p = pr.compute(inp(published=NOW - timedelta(hours=72), first_seen=NOW))
    assert codes(p)["stale"] == -20
    assert "stale" not in codes(pr.compute(inp(published=NOW - timedelta(hours=47), first_seen=NOW)))
    assert codes(pr.compute(inp(reliability="underground")))["underground_only"] == -10
    p = pr.compute(inp(reliability="underground", also_reported_by=[{"source": "ransomware.live"}]))
    assert "underground_only" not in codes(p)
    assert pr.compute(inp(severity="info", reliability="underground", published=NOW - timedelta(days=5))).score == 0


def test_global_scope_stays_low_without_watchlist_match():
    p = pr.compute(inp(scope="global", severity="critical", reliability="official", records=5_000_000))
    assert (p.score, p.band) == (39, "low")
    assert codes(p)["global_cap"] == 39 - 70
    p = pr.compute(inp(scope="global", severity="critical", watch_hits=[("product", "Fortinet FortiGate")]))
    assert p.band == "high" and "global_cap" not in codes(p)


def test_custom_weights_and_bands():
    p = pr.compute(inp(severity="high", countries=["UZ"]), {"country_uz": 50}, {"critical": 85})
    assert (p.score, p.band) == (85, "critical")
    assert pr.band_at_least("high", "medium") and not pr.band_at_least("medium", "high")
    assert pr.band_at_least(None, "low") and not pr.band_at_least(None, "medium")


@pytest.mark.parametrize("title,expected", [
    ('🇬🇳 GUINEA — CENTRAL BANK HACKER POSTS "ACT 2": 2.8GB SYRIF DATABASE, 8.3M RECORDS', 8_300_000),
    ("🇦🇺 SELLER CLAIMS 11M OPTUS CUSTOMER RECORDS FOR $46,000", 11_000_000),
    ('USA: SELLER CLAIMS 40M-RECORD "DME USA WIRELESS" CONSUMER DATABASE', 40_000_000),
    ("FRANCE: 44,080-MEMBER DATABASE OF SCOUTING GROUP EEDF", 44_080),
    ("Утечка: 1,2 млн записей клиентов банка", 1_200_000),
    ("Uber says 150 000 users affected", 150_000),
    ("Ransomware gang hits US hospital", None),
    ("Military university bought 200 chips, records show", None),
])
def test_record_count(title, expected):
    assert pr.record_count(title, "", {}) == expected


def test_record_count_prefers_structured_field():
    assert pr.record_count("x", "", {"pwn_count": 2_500_000}) == 2_500_000


def test_new_sectors():
    assert detect_sector("Хакеры атаковали энергетическую компанию") == "energy"
    assert detect_sector("Airport check-in systems down after cyberattack") == "transport"
    assert detect_sector("Uzbekistan airways") is None  # "airways" — kalit emas (shovqinsiz)


# ---------------------------------------------------------------- kuzatuv ro'yxati
def _w(kind, name, *aliases):
    return SimpleNamespace(id=None, kind=kind, name=name, aliases=list(aliases), country="UZ", enabled=True)


@pytest.mark.parametrize("entry,text,hit", [
    (_w("organisation", "Kapitalbank"), "Капиталбанк клиентларининг маълумотлари", True),  # lotin → kirill
    (_w("organisation", "Капиталбанк"), "Kapitalbank mijozlari", True),  # kirill → lotin
    (_w("organisation", "Soliq qo'mitasi"), "Soliq qoʻmitasi saytiga hujum", True),  # ʻ
    (_w("organisation", "Soliq qo'mitasi"), "soliq qomitasi bazasi", True),  # apostrofsiz
    (_w("brand", "Payme"), "Payment systems outage", False),  # butun so'z
    (_w("brand", "Payme"), "PAYME foydalanuvchilari", True),
    (_w("domain", "my.gov.uz"), "Phishing copy of https://my.gov.uz/ru/service", True),
    (_w("domain", "my.gov.uz"), "fake-my.gov.uzum.com", False),
    (_w("brand", "Uzcard", "Узкард"), "Мошенники от имени Узкард", True),
])
def test_watch_matching(entry, text, hit):
    assert bool(match(compile_watchlist([entry]), [text])) is hit


def test_watch_matches_extra_and_translations():
    w = compile_watchlist([_w("organisation", "Hamkorbank")])
    assert match(w, event_texts("Bank hit", "", [], {"victim": "hamkorbank.uz"}))
    assert match(w, event_texts("Банк атакован", "", [], {}, [("Hamkorbank attacked", None)]))
    assert not match(w, event_texts("Bank hit", "", [], {}))
    disabled = _w("organisation", "Hamkorbank")
    disabled.enabled = False
    assert compile_watchlist([disabled]) == []


# ---------------------------------------------------------------- bazada qayta hisoblash
async def _source(db, name="Kun.uz", kind="rss", reliability="media"):
    s = Source(name=name, kind=kind, config={"url": f"https://{name.lower()}.example/f"}, reliability=reliability)
    db.add(s)
    await db.commit()
    return s


async def test_store_items_scores_new_and_merged_events(db):
    s = await _source(db)
    now = datetime.now(UTC)
    item = RawItem(title="Hackers breach Uzbek bank: 1.5M records leaked", url="https://kun.example/a",
                   summary="O'zbekiston banki", published=now - timedelta(minutes=5), countries=["UZ"])
    await pipeline.store_items(db, s, [item], now, baseline=False)
    ev = await db.scalar(select(EventRecord))
    assert ev.priority_band is not None and ev.priority > 0
    got = codes(pr.Priority(ev.priority, ev.priority_band, ev.priority_reasons))
    assert got["country_uz"] == 30 and got["records_1m"] == 10 and "multi_source" not in got
    s2 = await _source(db, "Daryo")
    dup = RawItem(title="Hackers breach Uzbek bank: 1.5M records leaked", url="https://daryo.example/a",
                  summary="", published=now - timedelta(minutes=3), countries=["UZ"])
    await pipeline.store_items(db, s2, [dup], now, baseline=False)
    await db.refresh(ev)
    assert {r["code"] for r in ev.priority_reasons} >= {"multi_source"}


async def test_category_change_and_housekeeping_fill(db, client, admin_headers):
    s = await _source(db)
    cat = await db.scalar(select(Category).where(Category.slug == "other"))
    ev = EventRecord(uid="x1", source=s.name, source_id=s.id, category="other", category_id=cat.id, title="Hodisa",
                     url="https://kun.example/x", lang="uz", severity="info", countries=["UZ"])
    db.add(ev)
    await db.commit()
    assert ev.priority is None
    assert await scoring.missing_count(db) == 1
    assert await scoring.recompute(db, only_missing=True) == 1
    await db.refresh(ev)
    assert (ev.priority, ev.priority_band) == (30, "low")
    r = await client.patch(f"/api/events/{ev.id}", json={"category": "ransomware"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["priority"] == 80 and r.json()["priority_band"] == "critical"


async def test_watchlist_crud_recomputes_and_test_endpoint(db, client, admin_headers, analyst_headers):
    s = await _source(db)
    cat = await db.scalar(select(Category).where(Category.slug == "leak"))
    ev = EventRecord(uid="w1", source=s.name, source_id=s.id, category="leak", category_id=cat.id,
                     title="Uzum foydalanuvchilari ma'lumotlari sotuvda", url="https://kun.example/w", lang="uz",
                     severity="high", scope="regional", first_seen=datetime.now(UTC))
    db.add(ev)
    await db.commit()
    await scoring.recompute(db, [ev.id])
    await db.refresh(ev)
    assert ev.priority_band == "low"  # 35

    assert (await client.get("/api/admin/publisher/watchlist", headers=analyst_headers)).status_code == 403
    r = await client.post("/api/admin/publisher/watchlist", headers=admin_headers,
                          json={"kind": "brand", "name": "Uzum", "aliases": ["Узум", " uzum ", "Узум"], "country": "UZ"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["aliases"] == ["Узум", "uzum"] and "Узум" in body["terms"]
    await db.refresh(ev)
    assert ev.priority == 75 and ev.priority_band == "high"
    dup = await client.post("/api/admin/publisher/watchlist", headers=admin_headers, json={"kind": "brand", "name": "uzum"})
    assert dup.status_code == 409
    t = await client.get(f"/api/admin/publisher/watchlist/{body['id']}/test", headers=admin_headers)
    assert t.json()["total"] == 1 and t.json()["items"][0]["id"] == ev.id
    t = await client.post("/api/admin/publisher/watchlist/test", headers=admin_headers,
                          json={"kind": "brand", "name": "Payme"})
    assert t.json()["total"] == 0
    r = await client.patch(f"/api/admin/publisher/watchlist/{body['id']}", headers=admin_headers, json={"enabled": False})
    assert r.status_code == 200 and r.json()["enabled"] is False
    await db.refresh(ev)
    assert ev.priority_band == "low"
    assert (await client.delete(f"/api/admin/publisher/watchlist/{body['id']}", headers=admin_headers)).status_code == 200
    assert await db.scalar(select(WatchlistEntry.id)) is None


async def test_settings_get_put_validate_and_recompute(db, client, admin_headers):
    r = await client.get("/api/admin/publisher/settings", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["weights"]["severity"]["critical"] == 50 and body["bands"] == {"critical": 80, "high": 60, "medium": 40}
    assert await db.get(PublisherSettings, 1) is not None  # migratsiya seed qilgan
    s = await _source(db)
    cat = await db.scalar(select(Category).where(Category.slug == "leak"))
    ev = EventRecord(uid="s1", source=s.name, source_id=s.id, category="leak", category_id=cat.id, title="Leak",
                     url="https://kun.example/s", lang="uz", severity="high", countries=["UZ"],
                     first_seen=datetime.now(UTC))
    db.add(ev)
    await db.commit()
    body["bands"] = {"critical": 90, "high": 70, "medium": 50}
    body["weights"]["country_uz"] = 20
    r = await client.put("/api/admin/publisher/settings", headers=admin_headers,
                         json={"weights": body["weights"], "bands": body["bands"]})
    assert r.status_code == 200 and r.json()["bands"]["critical"] == 90
    await db.refresh(ev)
    assert (ev.priority, ev.priority_band) == (55, "medium")
    bad = {"weights": body["weights"], "bands": {"critical": 50, "high": 60, "medium": 40}}
    assert (await client.put("/api/admin/publisher/settings", headers=admin_headers, json=bad)).status_code == 422


async def test_source_reliability_seed_api_and_recompute(db, client, admin_headers):
    rel = dict((await db.execute(select(Source.name, Source.reliability))).all())
    assert rel["CISA KEV"] == "official" and rel["UZCERT"] == "official" and rel["ransomware.live"] == "tracker"
    assert rel.get("NewsNow: Cyber Attacks", "media") == "media"
    tg = (await db.execute(select(Source.reliability).where(Source.kind == "telegram_user"))).scalars().all()
    assert set(tg) <= {"community", "underground"}
    r = await client.post("/api/admin/sources", headers=admin_headers, json={
        "name": "KZ-CERT test", "kind": "rss", "config": {"url": "https://kz-cert.example/rss"}})
    assert r.status_code == 201, r.text
    assert r.json()["reliability"] == "official"
    sid = r.json()["id"]
    ev = EventRecord(uid="r1", source="KZ-CERT test", source_id=sid, category="other", title="Advisory",
                     url="https://kz-cert.example/1", lang="ru", severity="medium", countries=["KZ"],
                     first_seen=datetime.now(UTC))
    db.add(ev)
    await db.commit()
    await scoring.recompute(db, [ev.id])
    await db.refresh(ev)
    assert ev.priority == 45
    r = await client.patch(f"/api/admin/sources/{sid}", headers=admin_headers, json={"reliability": "media"})
    assert r.status_code == 200 and r.json()["reliability"] == "media"
    await db.refresh(ev)
    assert ev.priority == 35


async def test_events_api_band_filter_and_fields(db, client, analyst_headers):
    s = await _source(db)
    for i, (sev, band) in enumerate([("critical", None), ("info", None)]):
        db.add(EventRecord(uid=f"b{i}", source=s.name, source_id=s.id, category="other", title=f"E{i}",
                           url=f"https://kun.example/b{i}", lang="uz", severity=sev, countries=["UZ"]))
    await db.commit()
    await scoring.recompute(db, only_missing=True)
    r = await client.get("/api/events?band=critical,high", headers=analyst_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["title"] for i in items] == ["E0"] and items[0]["priority_band"] == "critical"
    assert items[0]["priority"] == 80
    assert {x["code"] for x in items[0]["priority_reasons"]} == {"sev_critical", "country_uz"}
    r = await client.get("/api/events?band=low", headers=analyst_headers)
    assert [i["title"] for i in r.json()["items"]] == ["E1"]
