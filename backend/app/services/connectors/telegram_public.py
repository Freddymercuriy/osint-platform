"""Ochiq Telegram kanal (login'siz, t.me/s/<kanal> sahifasi). config: {"channel": "kanal_username"}"""

from __future__ import annotations

import asyncio

from bs4 import BeautifulSoup

from app.services.connectors.base import ConfigError, Connector, FetchContext, FetchResult, RawItem, register
from app.services.events.filters import _clean, _parse_iso


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
        soup = await asyncio.to_thread(BeautifulSoup, resp.text, "html.parser")
        items: list[RawItem] = []
        for msg in soup.select("div.tgme_widget_message[data-post]"):
            text_el = msg.select_one("div.tgme_widget_message_text")
            if text_el is None:
                continue
            text = text_el.get_text(" ", strip=True)
            time_el = msg.select_one("a.tgme_widget_message_date time")
            first = text.split(". ")[0]
            items.append(RawItem(
                title=first[:140] + ("..." if len(first) > 140 else ""),
                url=f"https://t.me/{msg['data-post']}", summary=_clean(text),
                published=_parse_iso(time_el.get("datetime") if time_el else None),
                source_name=f"TG: {ctx.source.name}", channel="telegram_channel",
            ))
        return FetchResult(items, resp.status_code)
