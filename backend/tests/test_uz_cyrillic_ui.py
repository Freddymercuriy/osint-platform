"""O'zbek kirill interfeysi (`uz-Cyrl`) — latin.jaybi.uz dvigateli: himoyalangan o'girish, backend matnlari, API,
kategoriyalar, foydalanuvchi tili va UI xabarlari generatori."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.i18n import lang_from_header, t
from app.models import Category, EventRecord, EventTranslation
from app.services.i18n.text import uz_to_cyrillic


# ---------------------------------------------------------------- himoyalangan o'girish
@pytest.mark.parametrize("lat,cyr", [
    ("OSINT platformasi: API kaliti backend/.env faylida (TRANSLATE_API_URL)",
     "OSINT платформаси: API калити backend/.env файлида (TRANSLATE_API_URL)"),
    ("Google News orqali CVE-2026-1234 va 5G, RansomLook, UZCERT",
     "Google News орқали CVE-2026-1234 ва 5G, RansomLook, UZCERT"),
    ("O'ZBEKISTON RESPUBLIKASI ma'lumot, h.k.", "ЎЗБЕКИСТОН РЕСПУБЛИКАСИ маълумот, ҳ.к."),
    ("Akkaunt ID'si va username tarixi", "Аккаунт ID'си ва username тарихи"),
    ("masalan \"data-leak\"", "масалан \"data-leak\""),
    ("So'rovlar juda ko'p. {seconds} soniyadan keyin", "Сўровлар жуда кўп. {seconds} сониядан кейин"),
    ("<code>TG_API_ID</code> ni kiriting", "<code>TG_API_ID</code> ни киритинг"),
    ("Saytda https://gov.uz/o'zbek va @uzcert_uz. Oxiri.", "Сайтда https://gov.uz/o'zbek ва @uzcert_uz. Охири."),
    ("Kompyuter tizimiga kiberhujum: 15-iyuldagi hodisa", "Компьютер тизимига киберҳужум: 15-июлдаги ҳодиса"),
    # o'zbek lotinida yo'q harflar (c, w) — chet el nomi; o'zbekcha qisqartmalar — kirillga
    ("Tesla \" Cybercab \" ni sotdi, Facebook va Twitter orqali", "Тесла \" Cybercab \" ни сотди, Facebook ва Twitter орқали"),
    ("IIV, BMT va AQSh vakillari; Chilonzor", "ИИВ, БМТ ва АҚШ вакиллари; Чилонзор"),
    # so'zlar orasidagi "/" — fayl yo'li emas
    ("Ko'rsatish/yashirish, yoqish/o'chirish, CAPTCHA/Cloudflare", "Кўрсатиш/яшириш, ёқиш/ўчириш, CAPTCHA/Cloudflare"),
])
def test_uz_to_cyrillic_keeps_technical_tokens(lat, cyr):
    assert uz_to_cyrillic(lat) == cyr


# ---------------------------------------------------------------- backend matnlari
@pytest.mark.parametrize("header,lang", [
    ("uz-Cyrl", "uz-Cyrl"), ("uz-Cyrl-UZ,uz;q=0.8", "uz-Cyrl"), ("UZ-CYRL", "uz-Cyrl"), ("uz-Latn,uz-Cyrl;q=0.5", "uz"),
    ("ru,uz-Cyrl;q=0.9", "ru"), ("uz", "uz"),
])
def test_accept_language_uz_cyrl(header, lang):
    assert lang_from_header(header) == lang


def test_catalog_template_converted_params_untouched():
    assert t("too_many_requests", "uz-Cyrl", seconds=5) == "Сўровлар жуда кўп. 5 сониядан кейин қайта уриниб кўринг"
    # parametr qiymati (slug, domen ...) o'girilmaydi
    assert t("category_slug_not_found", "uz-Cyrl", slug="data-leak").endswith(": data-leak")
    assert t("category_slug_not_found", "uz-Cyrl", slug="qozoq").endswith(": qozoq")


async def test_error_detail_in_uz_cyrl(client):
    r = await client.get("/api/events", headers={"Accept-Language": "uz-Cyrl"})
    assert r.status_code == 401
    assert r.json()["detail"] == uz_to_cyrillic(t("not_authenticated", "uz")) == "Аутентификация талаб қилинади"


# ---------------------------------------------------------------- hodisalar
async def _event(db, uid: str, title: str, lang: str, summary: str = "") -> EventRecord:
    ev = EventRecord(uid=uid, source="S", category="other", title=title, url=f"https://x.example/{uid}", summary=summary,
                     lang=lang, severity="info")
    db.add(ev)
    await db.commit()
    return ev


async def test_events_api_uz_cyrl(client, analyst_headers, db):
    uz = await _event(db, "u1", "Toshkentda kiberjinoyatchilar qo'lga olindi", "uz", "Batafsil ma'lumot.")
    ru = await _event(db, "r1", "Хакеры атаковали банк", "ru")
    other = await _event(db, "r2", "Мошенники обманули жителей", "ru")
    db.add_all([
        EventTranslation(event_id=uz.id, lang="uz", title=uz.title, summary=uz.summary, provider="source", status="done"),
        EventTranslation(event_id=ru.id, lang="uz", title="Xakerlar bankka hujum qildi", summary="", provider="nllb",
                         status="done"),
        EventTranslation(event_id=other.id, lang="uz", title=None, summary=None, provider="none", status="pending"),
    ])
    await db.commit()

    r = await client.get("/api/events?lang=uz-Cyrl", headers=analyst_headers)
    assert r.status_code == 200, r.text
    items = {i["id"]: i for i in r.json()["items"]}
    a = items[uz.id]
    assert a["title"] == "Тошкентда кибержиноятчилар қўлга олинди" and a["summary"] == "Батафсил маълумот."
    assert a["display_lang"] == "uz-Cyrl" and a["translated"] is False and a["original_title"] == uz.title
    b = items[ru.id]
    assert b["title"] == "Хакерлар банкка ҳужум қилди" and b["display_lang"] == "uz-Cyrl" and b["translated"] is True
    c = items[other.id]  # o'zbekcha tarjima yo'q — asl matn, o'girilmaydi
    assert c["title"] == other.title and c["display_lang"] == "ru" and c["translation_status"] == "pending"

    assert (await client.get("/api/events?lang=uz-Latn", headers=analyst_headers)).status_code == 422
    n = await client.get("/api/notifications?lang=uz-Cyrl", headers=analyst_headers)
    assert n.status_code == 200
    latest = await client.get("/api/stats/latest?lang=uz-Cyrl&min_severity=info&range=90d", headers=analyst_headers)
    assert latest.status_code == 200


# ---------------------------------------------------------------- kategoriyalar va foydalanuvchi tili
async def test_categories_have_cyrillic_names(client, analyst_headers, admin_headers, db):
    rows = (await client.get("/api/categories", headers=analyst_headers)).json()
    leak = next(c for c in rows if c["slug"] == "leak")
    cat = await db.scalar(select(Category).where(Category.slug == "leak"))
    assert leak["name_uz_cyrl"] == uz_to_cyrillic(cat.name_uz) and leak["name_uz_cyrl"] != cat.name_uz
    assert "description_uz_cyrl" in leak
    admin_rows = (await client.get("/api/admin/categories", headers=admin_headers)).json()
    assert all("name_uz_cyrl" in c for c in admin_rows)


async def test_user_locale_uz_cyrl(client, make_user):
    _, headers = await make_user("cyr@example.com")
    r = await client.patch("/api/auth/me", json={"locale": "uz-Cyrl"}, headers=headers)
    assert r.status_code == 200 and r.json()["locale"] == "uz-Cyrl"
    assert (await client.patch("/api/auth/me", json={"locale": "uz-Latn"}, headers=headers)).status_code == 422


# ---------------------------------------------------------------- UI xabarlari generatori
def _generator():
    path = Path(__file__).resolve().parents[1] / "scripts" / "gen_uz_cyrl_messages.py"
    spec = importlib.util.spec_from_file_location("gen_uz_cyrl_messages", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("src,out", [
    ("{count, plural, one {# ta yozuv} other {# ta yozuv}} navbatga qaytarildi.",
     "{count, plural, one {# та ёзув} other {# та ёзув}} навбатга қайтарилди."),
    ("{n, select, news {Yangilik} other {Boshqa}}", "{n, select, news {Янгилик} other {Бошқа}}"),
    ("{used} / {limit}", "{used} / {limit}"),
    ("Oxirgi yangilanish: {when, date, short}", "Охирги янгиланиш: {when, date, short}"),
    ("backend/.env faylida <code>TRANSLATE_API_URL</code> ni ko'rsating", "backend/.env файлида <code>TRANSLATE_API_URL</code> ни кўрсатинг"),
    ("<b>Diqqat</b>: {count} ta hodisa", "<b>Диққат</b>: {count} та ҳодиса"),
])
def test_generator_keeps_icu_structure(src, out):
    assert _generator().convert_message(src) == out


def test_generator_preserves_language_names():
    gen = _generator()
    tree = {"locale": {"label": "Til", "uz": "O'zbekcha", "uz-Cyrl": "Ўзбекча"}, "nav": {"home": "Bosh sahifa"}}
    assert gen.convert_tree(tree) == {"locale": {"label": "Тил", "uz": "O'zbekcha", "uz-Cyrl": "Ўзбекча"},
                                      "nav": {"home": "Бош саҳифа"}}
