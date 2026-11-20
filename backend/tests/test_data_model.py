"""Bosqich 1: ma'lumot modeli — eski qatorlarni ko'chirish (0004), davlatlarni aniqlash, API maydonlari."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy import func, select

from app.models import Category, EventRecord, Source
from app.services.events.geo import detect_countries
from tests.conftest import ADMIN_DATABASE_URL, TEST_DATABASE_URL, _plain, scratch_db_name

ROOT = Path(__file__).resolve().parent.parent
SCRATCH_NAME = scratch_db_name("osint_datamodel_scratch")
SCRATCH = TEST_DATABASE_URL.rsplit("/", 1)[0] + f"/{SCRATCH_NAME}"


@pytest.mark.parametrize("text,expected", [
    ("Хакеры атаковали систему лесного хозяйства Узбекистана", ["UZ"]),
    ("Kazakh-linked hackers steal 2,000 files from Tajik govt", ["KZ", "TJ"]),
    ("Breach at bank.kg exposed records", ["KG"]),
    ("O‘zbekiston va Turkmaniston", ["UZ", "TM"]),
    ("Weight 5.kg is not a domain", []),
    ("Global ransomware report", []),
])
def test_detect_countries(text, expected):
    assert detect_countries(text) == expected


async def test_seed_categories_and_sources(db):
    slugs = (await db.scalars(select(Category.slug).order_by(Category.sort_order))).all()
    assert len(slugs) == 15 and slugs[-1] == "other"
    assert {"ransomware", "leak", "darkweb-sale", "credentials", "phishing", "fraud", "malware",
            "vulnerability", "ddos-outage", "defacement", "espionage", "law-enforcement", "advisory",
            "research", "other"} == set(slugs)
    n = await db.scalar(select(func.count(Source.id)))
    # v1 FEEDS + Bosqich 3 (0007) + NewsNow (0012) + DarkForums (0024); testda TG_CHATS bo'sh — yagona Telegram manbasi
    assert n == 63 + 15 + 1 + 1
    rl = await db.scalar(select(Source).where(Source.name == "ransomware.live"))
    assert rl.kind == "ransomware_live" and rl.config["countries"] == ["UZ", "KZ", "KG", "TJ", "TM"]
    assert rl.interval_seconds == 900 and rl.status == "never_run"
    gn = await db.scalar(select(Source).where(Source.name == "Google News (RU)"))
    assert gn.interval_seconds == 1800 and gn.cyber_filter and "query" in gn.config


async def _admin(sql: str) -> None:
    conn = await asyncpg.connect(_plain(ADMIN_DATABASE_URL))
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


def _migrate(*args: str) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "migrate.py"), *args],
                   cwd=ROOT, env=dict(os.environ, DATABASE_URL=SCRATCH), check=True, capture_output=True, text=True)


async def _q(sql: str, *args):
    conn = await asyncpg.connect(_plain(SCRATCH))
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


def test_legacy_rows_backfilled_and_restored():
    asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{SCRATCH_NAME}" WITH (FORCE)'))
    asyncio.run(_admin(f'CREATE DATABASE "{SCRATCH_NAME}"'))
    try:
        _migrate("0002_user_roles")
        legacy = [
            ("u1", "Gazeta.uz (RU)", "news", "Мошенники в Ташкенте", "🔎 мошенничество онлайн · В Ташкенте задержан"),
            ("u2", "Forbes.kz (Google News)", "news", "Атака на Forbes Kazakhstan", "🔎 хакер · "),
            ("u3", "TG: Some Chat", "tg_group", "Kazakhstan 1.2MLN leak", "🔎 kazakh, .kz · text"),
            ("u4", "ransomware.live", "ransomware", "[lockbit] Bank (KZ)", "victim"),
            ("u5", "UZCERT", "news", "Chrome zaiflik", "matn prefikssiz"),
        ]
        asyncio.run(_exec_many(
            "insert into events (uid, source, category, title, url, summary, lang, notified) "
            "values ($1, $2, $3, $4, 'https://x.example/', $5, 'ru', false)", legacy))
        _migrate()
        # 0005 uid'larni qayta hisoblaydi — qatorlar sarlavha bo'yicha topiladi
        by_title = {t[3]: t[0] for t in legacy}
        rows = {by_title[r["title"]]: r for r in asyncio.run(_q(
            "select e.title, e.summary, e.matched_keywords, e.channel, s.name as src, e.countries, "
            "c.slug as cat, e.severity from events e left join sources s on s.id = e.source_id "
            "left join categories c on c.id = e.category_id"))}
        assert rows["u1"]["summary"] == "В Ташкенте задержан"
        assert rows["u1"]["matched_keywords"] == ["мошенничество онлайн"]
        assert rows["u1"]["channel"] == "news" and rows["u1"]["src"] == "Gazeta.uz (RU)"
        assert rows["u1"]["countries"] == ["UZ"]
        assert rows["u2"]["summary"] == "" and rows["u2"]["src"] is None and rows["u2"]["countries"] == ["KZ"]
        assert rows["u3"]["channel"] == "telegram_group" and rows["u3"]["src"] == "Telegram (akkaunt)"
        assert rows["u3"]["matched_keywords"] == ["kazakh", ".kz"]
        assert rows["u4"]["channel"] == "api" and rows["u4"]["cat"] == "ransomware"
        assert rows["u4"]["severity"] == "critical"
        assert rows["u5"]["summary"] == "matn prefikssiz" and rows["u5"]["matched_keywords"] == []
        # 0008: eski news/telegram yozuvlari qoidalar bilan tasniflanadi, ransomware o'z kategoriyasida qoladi
        assert rows["u1"]["cat"] == "fraud" and rows["u4"]["cat"] == "ransomware"
        assert rows["u3"]["cat"] == "leak"

        _migrate("downgrade", "0002_user_roles")
        back = {by_title[r["title"]]: r["summary"] for r in asyncio.run(_q("select title, summary from events"))}
        cats_back = {by_title[r["title"]]: r["category"] for r in asyncio.run(_q("select title, category from events"))}
        assert cats_back["u1"] == "news" and cats_back["u3"] == "tg_group" and cats_back["u4"] == "ransomware"
        assert back["u1"] == "🔎 мошенничество онлайн · В Ташкенте задержан"
        assert back["u3"] == "🔎 kazakh, .kz · text"
        assert back["u5"] == "matn prefikssiz"
    finally:
        asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{SCRATCH_NAME}" WITH (FORCE)'))


async def _exec_many(sql: str, rows) -> None:
    conn = await asyncpg.connect(_plain(SCRATCH))
    try:
        await conn.executemany(sql, rows)
    finally:
        await conn.close()


async def test_events_api_exposes_v2_fields(client, analyst_headers, db):
    db.add(EventRecord(uid="x1", source="UZCERT", category="vulnerability", title="t", url="https://u.example/",
                       summary="s", lang="uz", countries=["UZ"], matched_keywords=["zaiflik"],
                       channel="news", severity="medium"))
    await db.commit()
    r = await client.get("/api/events", headers=analyst_headers)
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["category"] == "vulnerability" and item["countries"] == ["UZ"]
    assert item["matched_keywords"] == ["zaiflik"] and item["severity"] == "medium"
    assert item["channel"] == "news" and item["is_baseline"] is False


async def test_threat_intel_sources_seeded(db):
    rows = {s.name: s for s in (await db.scalars(select(Source))).all()}
    # kalit kerak, testda yo'q → o'chiq va auth_missing
    for name in ("ransomware.live PRO", "abuse.ch URLhaus (CA)", "abuse.ch ThreatFox (CA)",
                 "LevelBlue OTX pulses (Central Asia)", "Cloudflare Radar outages"):
        assert not rows[name].enabled and rows[name].status == "auth_missing", name
        assert rows[name].api_key_env
    for name in ("RansomLook", "Have I Been Pwned (breaches API)", "CISA KEV", "OpenPhish community feed",
                 "KG-CERT (KCOKB)", "Google News: KZ-CERT / STS"):
        assert rows[name].enabled and rows[name].status == "never_run", name
    assert rows["NVD critical CVEs"].status == "disabled" and not rows["NVD critical CVEs"].enabled
    assert rows["Kazakhstan STS (sts.kz)"].status == "blocked" and not rows["Kazakhstan STS (sts.kz)"].enabled
    assert rows["CISA KEV"].scope == "global"
    hibp_rss = rows["Have I Been Pwned"]
    assert not hibp_rss.enabled and hibp_rss.status == "disabled"
    assert rows["UZCERT"].config["default_countries"] == ["UZ"]
