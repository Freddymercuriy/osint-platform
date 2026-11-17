"""Hodisalar eksporti: Events filtrlari bilan bir xil, CSV formula injection himoyasi, JSON, chegara, ruxsat."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta

from app.models import EventRecord
from app.services.events import export


def _ev(uid, title, *, scope="regional", category="leak", hours=1, **kw):
    return EventRecord(uid=uid, source=kw.pop("source", "Kun.uz"), category=category, title=title,
                       url=f"https://x.example/{uid}", summary=kw.pop("summary", "matn"), lang="uz", scope=scope,
                       published=datetime.now(UTC) - timedelta(hours=hours), **kw)


async def _seed(db):
    db.add_all([
        _ev("a", "Bank ma'lumotlari sizdi", countries=["UZ"], matched_keywords=["uzbek", "leak"],
            also_reported_by=[{"source": "Daryo", "url": "https://d.example", "at": "2026-11-17T00:00:00+00:00"}]),
        _ev("b", "=HYPERLINK(\"http://evil.example\",\"click\")", category="phishing", hours=2,
            source="TG: chat", summary="+cmd|' /C calc'!A0"),
        _ev("c", "Global ransomware", scope="global", category="ransomware", hours=3),
    ])
    await db.commit()


def _rows(text: str) -> list[dict]:
    assert text.startswith("﻿")
    return list(csv.DictReader(io.StringIO(text[1:])))


async def test_csv_uses_events_filters_and_neutralizes_formulas(db, client, analyst_headers):
    await _seed(db)
    r = await client.get("/api/events/export", headers=analyst_headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"].startswith('attachment; filename="osint-events-')
    assert r.headers["x-export-total"] == "2" == r.headers["x-export-count"]  # standart: faqat regional
    rows = _rows(r.text)
    assert [x["title"] for x in rows] == ["Bank ma'lumotlari sizdi", "'=HYPERLINK(\"http://evil.example\",\"click\")"]
    assert rows[1]["summary"].startswith("'+cmd")
    assert rows[0]["countries"] == "UZ" and rows[0]["matched_keywords"] == "uzbek; leak"
    assert rows[0]["also_reported_by"] == "Daryo" and rows[0]["scope"] == "regional"

    r = await client.get("/api/events/export?scope=global&category=ransomware", headers=analyst_headers)
    assert [x["title"] for x in _rows(r.text)] == ["Global ransomware"]
    r = await client.get("/api/events/export?scope=all&q=bank", headers=analyst_headers)
    assert [x["id"] for x in _rows(r.text)] and len(_rows(r.text)) == 1


async def test_json_export_has_filters_and_truncation(db, client, analyst_headers, monkeypatch):
    await _seed(db)
    monkeypatch.setattr(export, "MAX_ROWS", 2)
    r = await client.get("/api/events/export?format=json&scope=all&range=7d", headers=analyst_headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert body["filters"] == {"scope": "all", "range": "7d"}
    assert (body["total"], body["count"], body["truncated"], body["max_rows"]) == (3, 2, True, 2)
    assert [x["title"] for x in body["items"]][0] == "Bank ma'lumotlari sizdi"  # eng yangisi birinchi
    assert body["items"][0]["title"] == "Bank ma'lumotlari sizdi"  # JSON'da formula himoyasi kerak emas
    assert body["items"][1]["title"].startswith("=HYPERLINK")


async def test_export_requires_login_and_validates_format(client, analyst_headers):
    assert (await client.get("/api/events/export")).status_code == 401
    assert (await client.get("/api/events/export?format=xlsx", headers=analyst_headers)).status_code == 422


def test_safe_cell():
    assert export.safe_cell("-2+3") == "'-2+3" and export.safe_cell("@SUM(A1)") == "'@SUM(A1)"
    assert export.safe_cell("\t=1") == "'\t=1" and export.safe_cell("Oddiy matn") == "Oddiy matn"
    assert export.safe_cell(None) == "" and export.safe_cell(["a", "b"]) == "a; b" and export.safe_cell(5) == "5"
