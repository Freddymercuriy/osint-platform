"""Ochiq Telegram kanal (login'siz, t.me/s/<kanal> sahifasi). config: {"channel": "kanal_username"}

Sarlavha — postning birinchi qatori (yangilik kanallarida bu maqola sarlavhasi), matn — qolgan qatorlar;
faqat havola yoki "Batafsil —" kabi xizmat qatorlari tashlanadi. Havola — `t.me/<kanal>/<id>` (post).
"""

from __future__ import annotations

import asyncio
import re

from bs4 import BeautifulSoup

from app.services.connectors.base import ConfigError, Connector, FetchContext, FetchResult, RawItem, register
from app.services.events.filters import _clean, _parse_iso

TITLE_LIMIT = 140
# Faqat havola / @kanal / "Batafsil — https://…", "👉 Obuna bo'ling — @kanal", "Подробнее:" kabi xizmat qatorlari
_NOISE_LINE = re.compile(
    r"^(?:[👉→⬇▶🔗➡️\s]*)"
    r"(?:https?://\S+|@\w+|[^\W\d_][\w '‘’ʻʼ`]{0,24}?\s*[—:→👉-]+(?:\s*(?:https?://\S+|@\w+))?|)$"
)


def _lines(text_el) -> list[str]:
    for br in text_el.find_all("br"):
        br.replace_with("\n")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text_el.get_text("").split("\n")]
    return [ln for ln in lines if ln and not _NOISE_LINE.match(ln)]


def parse_channel(html: str, source_name: str) -> list[RawItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[RawItem] = []
    for msg in soup.select("div.tgme_widget_message[data-post]"):
        text_el = msg.select_one("div.tgme_widget_message_text")
        if text_el is None:
            continue
        lines = _lines(text_el)
        if not lines:
            continue
        first = lines[0]
        title = first[:TITLE_LIMIT] + ("..." if len(first) > TITLE_LIMIT else "")
        body = " ".join(lines[1:]) if len(lines) > 1 else first
        time_el = msg.select_one("a.tgme_widget_message_date time")
        items.append(RawItem(
            title=title, url=f"https://t.me/{msg['data-post']}", summary=_clean(body),
            published=_parse_iso(time_el.get("datetime") if time_el else None),
            source_name=f"TG: {source_name}"[:128], channel="telegram_channel",
        ))
    return items


@register
class TelegramPublicConnector(Connector):
    kind = "telegram"
    title = "Ochiq Telegram kanal (t.me/s)"
    config_fields = ("channel",)

    def validate_config(self, config: dict) -> None:
        if not ((config or {}).get("channel") or "").strip().lstrip("@"):
            raise ConfigError("config.channel — kanal username'i kerak")

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        self.validate_config(ctx.source.config)
        channel = ctx.source.config["channel"].strip().lstrip("@")
        resp = await ctx.http.get(f"https://t.me/s/{channel}", expect_html=True)
        items = await asyncio.to_thread(parse_channel, resp.text, ctx.source.name)
        return FetchResult(items, resp.status_code)
