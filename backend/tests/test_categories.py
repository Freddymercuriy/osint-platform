"""Bosqich 4: klassifikator, kategoriyalar CRUD, qayta tasniflash, hodisalar filtrlari."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Category, EventRecord, Source
from app.services.events.classifier import RuleError, classify, compile_categories, validate_rules


@pytest.fixture
async def compiled(db):
    return compile_categories((await db.scalars(select(Category).order_by(Category.sort_order))).all())


@pytest.mark.parametrize("title,summary,expected", [
    ("Хакеры атаковали систему лесного хозяйства Узбекистана", "", "other"),
    ("Kazakhstan 1.2MLN citizen data leak", "", "leak"),
    ("Утечка персональных данных клиентов банка в Казахстане", "", "leak"),
    ("[lockbit5] Example Bank (KZ)", "ransomware victim", "ransomware"),
    ("Шифровальщик атаковал больницу в Бишкеке", "", "ransomware"),
    ("Мошенники похищают деньги через фальшивые ссылки в Telegram", "", "fraud"),
    ("В Узбекистане выявлены фишинговые сайты под видом Payme", "", "phishing"),
    ("Google Chrome brauzerida faol foydalanilayotgan kritik 0-day zaiflik aniqlandi!", "", "vulnerability"),
    ("CVE-2026-125350: Google Chromium Use-After-Free", "", "vulnerability"),
    ("Kazakhstan-linked hackers used AI agent to spy on Central Asian governments", "", "espionage"),
    ("Хакеры взломали почту госоргана Казахстана: эксперты связали атаку с ФСБ", "", "espionage"),
    ("В Ташкенте задержан хакер, взломавший аккаунты в Telegram", "", "law-enforcement"),
    ("Доступ к сети казахстанского оператора выставлен на продажу в даркнете", "", "darkweb-sale"),
    ("Infostealer logs with 40,000 Uzbek passwords posted", "", "credentials"),
    ("DDoS-атака: сайты госорганов Кыргызстана недоступны", "", "ddos-outage"),
    ("Хактивисты взломали сайт министерства и разместили дефейс", "", "defacement"),
    ("Генпрокуратура предупредила казахстанцев о новом законе", "", "advisory"),
    ("Эксперты представили отчёт о киберугрозах в Центральной Азии", "", "research"),
    ("Киберспорт: команда из Алматы выиграла турнир", "", "other"),
    ("Kazakhstan-Linked Hackers Use AI Agents to Steal Tajikistan Government Documents", "", "espionage"),
    ("2,000 documents related to Tajikistan's security stolen: Who is behind the cyberattack?", "", "leak"),
    ("Mirobod tumanida xalqaro kiberjinoiy guruhlar foş etildi – 72 kişi qölga olindi", "", "law-enforcement"),
])
async def test_classifier_examples(compiled, title, summary, expected):
    assert classify(title, summary, compiled).slug == expected


def test_validate_rules():
    ok = validate_rules({"stems": {"en": ["Phish ", "scam"]}, "patterns": [r"cve-\d+"], "weight": 2})
    assert ok["stems"]["en"] == ["phish ", "scam"] and ok["weight"] == 2.0 and ok["min_score"] == 1.0
    for bad in ({"patterns": ["("]}, {"stems": ["x"]}, {"weight": 100}, {"stems": {"en": [1]}}):
        with pytest.raises(RuleError):
            validate_rules(bad)


# ---------------------------------------------------------------- API
async def test_public_categories_list(client, analyst_headers):
    r = await client.get("/api/categories", headers=analyst_headers)
    data = r.json()
    assert r.status_code == 200 and len(data) == 15 and data[-1]["slug"] == "other"
    assert {"name_en", "name_ru", "name_uz", "severity", "color", "icon", "event_count"} <= set(data[0])
    assert "rules" not in data[0]


ADMIN_ROUTES = [("get", "/api/admin/categories"), ("post", "/api/admin/categories"),
                ("get", "/api/admin/categories/1"), ("patch", "/api/admin/categories/1"),
                ("delete", "/api/admin/categories/1"), ("post", "/api/admin/categories/reorder"),
                ("post", "/api/admin/categories/reclassify"), ("patch", "/api/events/1")]


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
async def test_category_admin_routes_require_admin(client, analyst_headers, method, path):
    kw = {"json": {}} if method in ("post", "patch") else {}
    assert (await client.request(method.upper(), path, **kw)).status_code == 401
    assert (await client.request(method.upper(), path, headers=analyst_headers, **kw)).status_code == 403


NEW = {"slug": "crypto-theft", "name_en": "Crypto theft", "name_ru": "Кража криптовалюты",
       "name_uz": "Kriptovalyuta o'g'irligi", "severity": "high", "color": "purple", "icon": "Bitcoin",
       "rules": {"stems": {"en": ["crypto", "bitcoin"], "ru": ["криптовалют"]}, "weight": 1.5}}


async def test_crud_reorder_and_delete_moves_to_other(client, admin_headers, db):
    r = await client.post("/api/admin/categories", json=NEW, headers=admin_headers)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.post("/api/admin/categories", json=NEW, headers=admin_headers)).status_code == 409
    for bad in ({**NEW, "slug": "Bad Slug"}, {**NEW, "slug": "x2", "color": "neon"},
                {**NEW, "slug": "x3", "rules": {"patterns": ["("]}}, {**NEW, "slug": "x4", "icon": "bad icon"}):
        assert (await client.post("/api/admin/categories", json=bad, headers=admin_headers)).status_code == 422

    db.add(EventRecord(uid="c1", source="S", category="crypto-theft", category_id=cid, title="Bitcoin stolen",
                       url="https://x.example/1", summary="", lang="en", severity="high"))
    await db.commit()

    r = await client.patch(f"/api/admin/categories/{cid}", json={"severity": "critical", "name_uz": "Kripto"},
                           headers=admin_headers)
    assert r.json()["severity"] == "critical" and r.json()["event_count"] == 1
    ev = await db.scalar(select(EventRecord).where(EventRecord.uid == "c1"))
    await db.refresh(ev)
    assert ev.severity == "critical"

    ids = [c["id"] for c in (await client.get("/api/admin/categories", headers=admin_headers)).json()]
    new_order = [cid] + [i for i in ids if i != cid]
    r = await client.post("/api/admin/categories/reorder", json={"ids": new_order}, headers=admin_headers)
    assert r.json()[0]["id"] == cid

    r = await client.delete(f"/api/admin/categories/{cid}", headers=admin_headers)
    assert r.json() == {"moved_to_other": 1}
    await db.refresh(ev)
    assert ev.category == "other" and ev.severity == "info"

    leak = await db.scalar(select(Category).where(Category.slug == "leak"))
    assert (await client.delete(f"/api/admin/categories/{leak.id}", headers=admin_headers)).status_code == 409
    r = await client.patch(f"/api/admin/categories/{leak.id}", json={"enabled": False}, headers=admin_headers)
    assert r.json()["enabled"] is False
    other = await db.scalar(select(Category).where(Category.slug == "other"))
    assert (await client.patch(f"/api/admin/categories/{other.id}", json={"enabled": False},
                               headers=admin_headers)).status_code == 409


async def test_reclassify_dry_run_then_apply_respects_lock(client, admin_headers, db):
    ev = [
        EventRecord(uid="r1", source="S", category="other", title="Фишинговые сайты под видом банка",
                    url="https://x.example/1", summary="", lang="ru"),
        EventRecord(uid="r2", source="S", category="other", title="Фишинговая рассылка от имени налоговой",
                    url="https://x.example/2", summary="", lang="ru", category_locked=True),
        EventRecord(uid="r3", source="S", category="ransomware", title="[akira] Some Org (KZ)",
                    url="https://x.example/3", summary="", lang="en", extra={"fixed_category": "ransomware"}),
    ]
    db.add_all(ev)
    await db.commit()
    r = await client.post("/api/admin/categories/reclassify", headers=admin_headers)
    body = r.json()
    assert body["dry_run"] and body["changed"] == 1 and body["transitions"] == {"other→phishing": 1}
    assert body["locked_skipped"] == 1 and body["samples"][0]["to"] == "phishing"
    await db.refresh(ev[0])
    assert ev[0].category == "other"  # dry run hech narsa yozmaydi

    r = await client.post("/api/admin/categories/reclassify?dry_run=false", headers=admin_headers)
    assert r.json()["changed"] == 1
    for e in ev:
        await db.refresh(e)
    assert ev[0].category == "phishing" and ev[0].severity == "medium" and ev[0].category_id is not None
    assert ev[1].category == "other" and ev[2].category == "ransomware"


async def test_manual_category_change_locks(client, admin_headers, db):
    e = EventRecord(uid="m1", source="S", category="other", title="Something", url="https://x.example/m",
                    summary="", lang="en", extra={"severity_floor": "high"})
    db.add(e)
    await db.commit()
    r = await client.patch(f"/api/events/{e.id}", json={"category": "advisory"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["category"] == "advisory"
    await db.refresh(e)
    assert e.category_locked and e.severity == "high"  # ulagich ko'targan daraja saqlanadi
    assert (await client.patch(f"/api/events/{e.id}", json={"category": "nope"},
                               headers=admin_headers)).status_code == 422


# ---------------------------------------------------------------- filtrlar
async def test_event_filters_combine(client, analyst_headers, db):
    now = datetime.now(UTC)
    src = await db.scalar(select(Source).where(Source.name == "UZCERT"))
    rows = [
        dict(uid="f1", category="phishing", severity="medium", countries=["UZ"], channel="news", scope="regional",
             lang="ru", source="UZCERT", source_id=src.id, title="Фишинг 50% скидка", published=now - timedelta(days=1)),
        dict(uid="f2", category="ransomware", severity="critical", countries=["KZ"], channel="api", scope="regional",
             lang="en", source="RansomLook", title="[akira] Org (KZ)", actor="akira", published=now - timedelta(days=3)),
        dict(uid="f3", category="vulnerability", severity="high", countries=[], channel="api", scope="global",
             lang="en", source="CISA KEV", title="CVE-2026-1: Product", published=now - timedelta(days=2)),
        dict(uid="f4", category="fraud", severity="medium", countries=["UZ", "KZ"], channel="telegram_group",
             scope="regional", lang="uz", source="TG: chat", title="firibgarlar", published=now - timedelta(days=10)),
    ]
    for r in rows:
        db.add(EventRecord(url=f"https://x.example/{r['uid']}", summary="", **r))
    await db.commit()

    async def ids(qs: str) -> list[str]:
        r = await client.get(f"/api/events?{qs}", headers=analyst_headers)
        assert r.status_code == 200, r.text
        return sorted(i["title"][:6] for i in r.json()["items"])

    assert len(await ids("")) == 3  # standart: faqat regional
    assert await ids("scope=global") == ["CVE-20"]
    assert len(await ids("scope=all")) == 4
    assert await ids("category=phishing,fraud&country=UZ") == ["firibg", "Фишинг"]
    assert await ids("severity=critical&scope=all") == ["[akira"]
    assert await ids("channel=telegram_group") == ["firibg"]
    assert await ids("category=tg_group") == ["firibg"]  # v1 tab → kanal
    assert await ids(f"source={src.id}") == ["Фишинг"]
    assert await ids("source=RansomLook") == ["[akira"]
    assert await ids("lang=uz&lang=ru") == ["firibg", "Фишинг"]
    d = (now - timedelta(days=5)).date().isoformat()
    assert len(await ids(f"date_from={d}")) == 2
    assert await ids(f"date_to={d}") == ["firibg"]
    assert await ids("q=akira") == ["[akira"]
    assert await ids("q=50%25") == ["Фишинг"]
    assert await ids("q=%25") == ["Фишинг"]  # % — oddiy belgi (faqat "50%" sarlavhasida bor), wildcard emas
    assert await ids("q=_") == []  # _ ham wildcard emas
    r = await client.get("/api/events?scope=bad", headers=analyst_headers)
    assert r.status_code == 422


async def test_pipeline_classifies_new_items(db, monkeypatch):
    import httpx

    from app.services.events import scheduler
    from tests.helpers import ago, rss, use_transport

    s = Source(name="Cls test", kind="rss", config={"url": "https://feed.example/rss"}, lang="ru",
               interval_seconds=600, baseline_done=True)
    vuln = await db.scalar(select(Category).where(Category.slug == "vulnerability"))
    f = Source(name="Fixed test", kind="rss", config={"url": "https://fixed.example/rss"}, lang="ru",
               interval_seconds=600, baseline_done=True, category_id=vuln.id)
    db.add_all([s, f])
    await db.commit()
    titles = {"feed.example": "Фишинговые сайты под видом Payme атакуют узбекистанцев",
              "fixed.example": "Обновление безопасности для роутеров вышло в Ташкенте"}
    use_transport(monkeypatch, lambda req: httpx.Response(200, content=rss([
        (titles[req.url.host], f"https://{req.url.host}/1", ago(hours=1)),
    ])))
    await scheduler.run_source(s.id)
    await scheduler.run_source(f.id)
    a = await db.scalar(select(EventRecord).where(EventRecord.source_id == s.id))
    b = await db.scalar(select(EventRecord).where(EventRecord.source_id == f.id))
    assert a.category == "phishing" and a.severity == "medium" and a.extra["classifier"]["score"] > 0
    assert "fixed_category" not in a.extra
    assert b.category == "vulnerability" and b.extra["fixed_category"] == "vulnerability"


async def test_reclassify_keeps_connector_severity_floor(client, admin_headers, db):
    vuln = await db.scalar(select(Category).where(Category.slug == "vulnerability"))
    e = EventRecord(uid="k1", source="CISA KEV", category="vulnerability", category_id=vuln.id, severity="high",
                    title="CVE-2026-1: Product", url="https://x.example/k", summary="", lang="en", scope="global",
                    extra={"fixed_category": "vulnerability", "severity_floor": "high"})
    db.add(e)
    await db.commit()
    r = await client.post("/api/admin/categories/reclassify?dry_run=false", headers=admin_headers)
    assert r.json()["severity_changed"] == 0
    await db.refresh(e)
    assert e.severity == "high"
