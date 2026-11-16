"""latin.jaybi.uz dvigateli (vendor/uztranslit.py) — yuqori oqimning conformance to'plami (spec/fixtures.json, o'sha commit).

Vendored fayl o'zgartirilmagan; bu test uni yangilaganda (yoki Python versiyasi o'zgarganda) xatoni darhol ko'rsatadi.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.i18n.text import uz_to_cyrillic, uz_to_latin
from app.services.i18n.vendor import uztranslit as U

FX = json.loads((Path(__file__).parent / "fixtures" / "uztranslit_fixtures.json").read_text(encoding="utf-8"))


# Har guruh — bitta test (har test uchun baza tozalanadi; 246 ta alohida test to'plamni bekorga sekinlatardi),
# lekin barcha nomuvofiqliklar bitta ro'yxatda chiqadi.
def _report(fails: list[str]) -> None:
    assert not fails, f"{len(fails)} ta nomuvofiqlik:\n" + "\n".join(fails[:20])


def test_cases():
    fails = []
    for c in FX["cases"]:
        got = U.convert(c["in"], c["from"], c["to"])
        if got != c["out"]:
            fails.append(f"{c['id']} {c['from']}->{c['to']} {c['in']!r}: want {c['out']!r}, got {got!r}")
    assert len(FX["cases"]) >= 200
    _report(fails)


def test_roundtrips_detect_optional():
    fails = []
    for r in FX["roundtrips"]:
        there = U.convert(r["in"], r["from"], r["via"])
        back = U.convert(there, r["via"], r["from"])
        if back != r["in"]:
            fails.append(f"{r['id']}: {r['in']!r} -> {there!r} -> {back!r}")
    for d in FX["detect"]:
        if U.detect(d["in"]) != d["expect"]:
            fails.append(f"detect {d['in']!r}: want {d['expect']}")
    for o in FX["optional"]:
        options = {"okina": "'", "tutuq": "'"} if o["feature"] == "asciiApostrophe" else {"skipUrls": True}
        got = U.convert(o["in"], o["from"], o["to"], options)
        if got != o["out"]:
            fails.append(f"optional/{o['feature']}: want {o['out']!r}, got {got!r}")
    _report(fails)


@pytest.mark.parametrize("lat,cyr", [
    ("Toshkentda kiberjinoyatchilar qo'lga olindi.", "Тошкентда кибержиноятчилар қўлга олинди."),
    ("Kompyuter tizimiga kiberhujum: 15-iyuldagi hodisa", "Компьютер тизимига киберҳужум: 15-июлдаги ҳодиса"),
    ("Toşkent şahri", "Тошкент шаҳри"),  # 2026 lotin alifbosi ham
    ("Saytda https://gov.uz/o'zbek va @uzcert_uz", "Сайтда https://gov.uz/o'zbek ва @uzcert_uz"),  # URL/username tegilmaydi
    ("Тошкент шаҳри", "Тошкент шаҳри"),  # allaqachon kirill
])
def test_uz_to_cyrillic(lat, cyr):
    assert uz_to_cyrillic(lat) == cyr


def test_uz_to_latin_uses_ascii_apostrophes():
    assert uz_to_latin("Ўзбекистонда кибержиноятчилар қўлга олинди. Сентябрь, цирк, объект.") == \
        "O'zbekistonda kiberjinoyatchilar qo'lga olindi. Sentabr, sirk, obyekt."
    assert uz_to_latin("") == "" and uz_to_cyrillic(None) == ""
