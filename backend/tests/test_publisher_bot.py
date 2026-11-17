"""Bot API mijozi: xato turlari va token hech qayerga (xato matni, traceback, log) tushmasligi."""

from __future__ import annotations

import json
import logging
import traceback

import httpx
import pytest

from app.core.config import settings
from app.services.publisher import bot

TOKEN = "123456789:AAH-fake_TOKEN_value_abcdefghijklmnopqr"


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setattr(settings, "tg_bot_token", TOKEN)


def _client(handler) -> bot.BotClient:
    return bot.BotClient(TOKEN, transport=httpx.MockTransport(handler))


def _json(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body)


async def test_success_and_request_shape():
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path.endswith("/getMe"):
            return _json(200, {"ok": True, "result": {"id": 1, "is_bot": True, "username": "osint_test_bot"}})
        return _json(200, {"ok": True, "result": {
            "message_id": 42, "chat": {"id": -1001}, "date": 1, "text": "Salom",
            "entities": [{"type": "bold", "offset": 0, "length": 5}]}})

    c = _client(handler)
    me = await c.get_me()
    assert me["username"] == "osint_test_bot"
    sent = await c.send_message(-1001, "<b>Salom</b>", silent=True, reply_to=7,
                                reply_markup={"inline_keyboard": [[{"text": "Manba", "url": "https://x.uz"}]]})
    assert sent.message_id == 42 and sent.entities[0]["type"] == "bold"
    body = json.loads(seen[-1].content)
    assert body["parse_mode"] == "HTML" and body["link_preview_options"] == {"is_disabled": True}
    assert body["disable_notification"] is True and "protect_content" not in body
    assert body["reply_parameters"] == {"message_id": 7, "allow_sending_without_reply": True}
    assert seen[-1].url.path == f"/bot{TOKEN}/sendMessage"
    await c.aclose()


async def test_send_photo_is_multipart_with_json_fields():
    seen: list[httpx.Request] = []

    def handler(req):
        seen.append(req)
        return _json(200, {"ok": True, "result": {"message_id": 5, "chat": {"id": -1}, "caption": "Hafta"}})

    c = _client(handler)
    sent = await c.send_photo(-1, b"\x89PNG fake", caption="<b>Hafta</b>",
                              reply_markup={"inline_keyboard": [[{"text": "a", "url": "https://a.uz"}]]})
    raw = seen[0].content
    assert seen[0].headers["content-type"].startswith("multipart/form-data")
    assert b'filename="chart.png"' in raw and b'{"inline_keyboard"' in raw and sent.text == "Hafta"
    await c.aclose()


ERRORS = [
    (_json(429, {"ok": False, "error_code": 429, "description": "Too Many Requests: retry after 7",
                 "parameters": {"retry_after": 7}}), bot.BotRateLimited),
    (_json(401, {"ok": False, "error_code": 401, "description": f"Unauthorized {TOKEN}"}), bot.BotUnauthorized),
    (_json(404, {"ok": False, "error_code": 404, "description": "Not Found"}), bot.BotUnauthorized),
    (_json(403, {"ok": False, "error_code": 403, "description": "Forbidden: bot was kicked from the channel chat"}),
     bot.BotForbidden),
    (_json(400, {"ok": False, "error_code": 400,
                 "description": "Bad Request: can't parse entities: Unsupported start tag \"x\" at byte offset 3"}),
     bot.BotBadRequest),
    (_json(400, {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}), bot.BotBadRequest),
    (_json(409, {"ok": False, "error_code": 409,
                 "description": "Conflict: can't use getUpdates method while webhook is active"}), bot.BotConflict),
    (httpx.Response(502, text=f"<html>Bad Gateway https://api.telegram.org/bot{TOKEN}/x</html>"), bot.BotNetworkError),
]


@pytest.mark.parametrize("response,exc_type", ERRORS)
async def test_error_types_never_leak_token(response, exc_type, caplog):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="httpx")
    c = _client(lambda req: response)
    with pytest.raises(exc_type) as info:
        await c.send_message("-100123", "x")
    exc = info.value
    logging.getLogger("osint.publisher").warning("Yuborilmadi: %s", exc)
    logging.getLogger("osint.publisher").exception("Yuborilmadi", exc_info=exc)
    stored = {"last_error": str(exc), "description": exc.description, "repr": repr(exc),
              "tb": "".join(traceback.format_exception(exc))}
    assert TOKEN not in json.dumps(stored)
    assert TOKEN not in caplog.text
    assert "api.telegram.org" in caplog.text or exc_type is not bot.BotNetworkError  # httpx INFO logi bor, tokensiz
    if exc_type is bot.BotRateLimited:
        assert exc.retry_after == 7
    if exc_type is bot.BotBadRequest:
        assert exc.is_parse_error or exc.chat_not_found
    await c.aclose()


@pytest.mark.parametrize("raised", [
    httpx.ConnectError(f"All connection attempts failed for https://api.telegram.org/bot{TOKEN}/sendMessage"),
    httpx.ReadTimeout(f"timed out https://api.telegram.org/bot{TOKEN}/sendMessage"),
])
async def test_network_errors_are_redacted(raised, caplog):
    caplog.set_level(logging.DEBUG)

    def handler(req):
        raise raised

    c = _client(handler)
    with pytest.raises(bot.BotNetworkError) as info:
        await c.get_me()
    logging.getLogger("osint.publisher").exception("Tarmoq", exc_info=info.value)
    assert info.value.__cause__ is None and info.value.__suppress_context__
    assert TOKEN not in str(info.value) and TOKEN not in caplog.text
    assert TOKEN not in "".join(traceback.format_exception(info.value))
    await c.aclose()


def test_redact_and_missing_token(monkeypatch):
    assert bot.redact(f"x {TOKEN} y") == "x <token> y"
    assert bot.redact("other 987654321:ZZZ-another_token_value_abcdefghijk") == "other <token>"
    assert "<token>" not in bot.redact("CVE-2026-12345 va 2026-11-17 14:05")
    assert repr(bot.BotClient(TOKEN)) == "BotClient(<token>)"
    monkeypatch.setattr(settings, "tg_bot_token", None)
    assert not bot.token_configured()
    with pytest.raises(bot.BotTokenMissing):
        bot.make_client()
