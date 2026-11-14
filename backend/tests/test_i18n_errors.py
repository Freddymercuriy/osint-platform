"""Lokalizatsiya: Accept-Language, kodli xatolar, katalog to'liqligi, collector yorliqlari."""

import string

import pytest

from app.core.i18n import LANGS, MESSAGES, CodedValueError, current_lang, lang_from_header, set_lang, t


# ---------------------------------------------------------------- Accept-Language
@pytest.mark.parametrize("header,expected", [
    (None, "uz"),
    ("", "uz"),
    ("ru", "ru"),
    ("ru-RU,ru;q=0.9,en;q=0.8", "ru"),
    ("en-US,en;q=0.9,ru;q=0.8", "en"),
    ("de,en;q=0.5", "en"),
    ("fr,de", "uz"),
    ("en;q=0.3, ru;q=0.7", "ru"),
    ("ru;q=0, en;q=0.1", "en"),
    ("*", "uz"),
    ("ru;q=abc, en", "en"),
    ("EN", "en"),
])
def test_lang_from_header(header, expected):
    assert lang_from_header(header) == expected


def test_t_params_and_fallbacks():
    assert t("category_slug_not_found", "ru", slug="x") == "Категория не найдена: x"
    assert t("source_not_found") == "Manba topilmadi"
    assert t("no-such-code", "en") == "no-such-code"
    assert t("source_not_found", "xx") == "Manba topilmadi"
    assert t("c_phone_intl", "en") == "International: {number}"  # parametr yetishmasa — yiqilmaydi
    set_lang("ru")
    assert current_lang() == "ru"
    set_lang("uz")


def test_coded_value_error():
    exc = CodedValueError("invalid_username_query")
    assert exc.code == "invalid_username_query"
    assert str(exc) == t("invalid_username_query", "uz")


# ---------------------------------------------------------------- katalog
def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}


def test_catalogue_complete():
    assert len(MESSAGES) > 100
    for code, langs in MESSAGES.items():
        assert set(langs) == set(LANGS), code
        assert all(isinstance(v, str) and v.strip() for v in langs.values()), code
        assert _fields(langs["ru"]) == _fields(langs["uz"]) == _fields(langs["en"]), code


# ---------------------------------------------------------------- endpointlar
async def _check(r, status, code, lang_texts, lang):
    assert r.status_code == status, r.text
    body = r.json()
    assert body["code"] == code
    assert isinstance(body["detail"], str)
    assert body["detail"] == lang_texts[lang]


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
async def test_login_wrong_password(client, make_user, lang):
    await make_user("u@example.com", password="right-password")
    r = await client.post(
        "/api/auth/login", data={"username": "u@example.com", "password": "wrong-password"},
        headers={"Accept-Language": lang},
    )
    await _check(r, 401, "invalid_credentials", MESSAGES["invalid_credentials"], lang)


async def test_login_default_language_is_uz(client):
    r = await client.post("/api/auth/login", data={"username": "no@example.com", "password": "x"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Email yoki parol noto'g'ri", "code": "invalid_credentials"}


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
async def test_register_duplicate(client, make_user, lang):
    await make_user("Dup@Example.com")
    r = await client.post(
        "/api/auth/register", json={"email": "dup@example.com", "password": "password-123"},
        headers={"Accept-Language": lang},
    )
    await _check(r, 409, "email_taken", MESSAGES["email_taken"], lang)


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
async def test_admin_only_as_analyst(client, analyst_headers, lang):
    r = await client.get("/api/admin/sources", headers={**analyst_headers, "Accept-Language": lang})
    await _check(r, 403, "admin_only", MESSAGES["admin_only"], lang)


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
async def test_unknown_source(client, admin_headers, lang):
    r = await client.get("/api/admin/sources/999999", headers={**admin_headers, "Accept-Language": lang})
    await _check(r, 404, "source_not_found", MESSAGES["source_not_found"], lang)


async def test_unknown_category_with_param(client, admin_headers):
    r = await client.patch(
        "/api/admin/categories/999999", json={"name_uz": "x"},
        headers={**admin_headers, "Accept-Language": "en-US,en;q=0.9"},
    )
    assert r.status_code == 404
    assert r.json() == {"detail": "Category not found", "code": "category_not_found"}


async def test_no_token_is_coded_401(client):
    r = await client.get("/api/auth/me", headers={"Accept-Language": "ru"})
    assert r.status_code == 401
    assert r.json() == {"detail": "Требуется аутентификация", "code": "not_authenticated"}
    assert r.headers["www-authenticate"] == "Bearer"


async def test_invalid_token_is_coded_401(client):
    r = await client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_token"


async def test_validation_error_keeps_detail_list(client):
    r = await client.post("/api/auth/register", json={"email": "not-an-email"})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation_error"
    assert isinstance(body["detail"], list) and body["detail"]


async def test_collector_query_error_is_coded(client, analyst_headers):
    r = await client.post(
        "/api/search/username", json={"query": "bad name!"},
        headers={**analyst_headers, "Accept-Language": "ru"},
    )
    assert r.status_code == 422, r.text
    assert r.json() == {"detail": t("invalid_telegram_query", "ru"), "code": "invalid_telegram_query"}


async def test_plain_http_error_gets_code(client):
    r = await client.get("/no/such/route")
    assert r.status_code == 404
    assert r.json()["code"] == "http_404"


# ---------------------------------------------------------------- collector yorliqlari (tarmoqsiz)
async def test_phone_labels_follow_language(client, analyst_headers):
    sources = {}
    for lang in LANGS:
        r = await client.post(
            "/api/search/phone", json={"query": "+998901234567"},
            headers={**analyst_headers, "Accept-Language": lang},
        )
        assert r.status_code == 200, r.text
        sources[lang] = [x["source"] for x in r.json()["results"]]
    assert "Yaroqlilik" in sources["uz"] and "Raqam turi" in sources["uz"]  # uz — avvalgidek
    assert "Валидность" in sources["ru"]
    assert "Validity" in sources["en"]
    assert sources["ru"] != sources["en"] != sources["uz"]


async def test_phone_unparsable_detail_localised(client, analyst_headers):
    r = await client.post(
        "/api/search/phone", json={"query": "abc"}, headers={**analyst_headers, "Accept-Language": "en"}
    )
    assert r.status_code == 200
    res = r.json()["results"][0]
    assert res["source"] == "Parsing" and res["status"] == "error"
    assert res["detail"].startswith("Could not parse the number")
