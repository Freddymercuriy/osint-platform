"""Foydalanuvchining o'z Telegram akkaunti orqali (MTProto, Telethon) o'qish.

Login bir marta `scripts/tg_login.py` bilan interaktiv qilinadi — session fayli
`settings.tg_session_path` ga saqlanadi. Bu fayl akkauntga TO'LIQ kirish beradi:
hech qachon git'ga qo'shilmaydi va hech kimga berilmaydi.

Maxfiylik: guruhlardagi xabar yuboruvchilarning ismi/telefoni saqlanmaydi va
ko'rsatilmaydi — faqat xabar matni (filtrdan o'tganlari) va havola.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

from app.core.config import settings

_client: TelegramClient | None = None
_lock = asyncio.Lock()


class TelegramNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.tg_api_id and settings.tg_api_hash)


def session_exists() -> bool:
    return Path(settings.tg_session_path + ".session").exists()


async def get_client() -> TelegramClient:
    """Ulangan va avtorizatsiyadan o'tgan klientni qaytaradi (yagona nusxa)."""
    global _client
    if not is_configured():
        raise TelegramNotConfigured("TG_API_ID / TG_API_HASH .env da sozlanmagan")
    async with _lock:
        if _client is None:
            Path(settings.tg_session_path).parent.mkdir(parents=True, exist_ok=True)
            _client = TelegramClient(
                settings.tg_session_path, settings.tg_api_id, settings.tg_api_hash
            )
        if not _client.is_connected():
            await _client.connect()
        if not await _client.is_user_authorized():
            raise TelegramNotConfigured(
                "Telegram akkaunti login qilinmagan — scripts/tg_login.py ni ishga tushiring"
            )
        return _client


@dataclass
class ChatInfo:
    id: int
    title: str
    username: str | None
    kind: str  # "channel" | "group"


@dataclass
class TgMessage:
    chat: ChatInfo
    msg_id: int
    text: str
    date: datetime | None

    @property
    def url(self) -> str:
        if self.chat.username:
            return f"https://t.me/{self.chat.username}/{self.msg_id}"
        # Yopiq chat — havola faqat a'zolar uchun ishlaydi
        internal = str(abs(self.chat.id))
        if internal.startswith("100"):
            internal = internal[3:]
        return f"https://t.me/c/{internal}/{self.msg_id}"


def _chat_info(dialog) -> ChatInfo | None:
    ent = dialog.entity
    if isinstance(ent, Channel):
        kind = "group" if ent.megagroup else "channel"
    elif isinstance(ent, Chat):
        kind = "group"
    else:
        return None  # shaxsiy suhbatlar (user/bot) o'qilmaydi
    return ChatInfo(
        id=dialog.id,
        title=dialog.name or "?",
        username=getattr(ent, "username", None),
        kind=kind,
    )


async def list_chats() -> list[ChatInfo]:
    client = await get_client()
    chats: list[ChatInfo] = []
    async for d in client.iter_dialogs(limit=settings.tg_dialog_limit):
        info = _chat_info(d)
        if info:
            chats.append(info)
    return chats


def chat_matches(info: ChatInfo, keys: list[str]) -> bool:
    """Chat username yoki ID bo'yicha ro'yxatda bormi."""
    return (info.username or "").lower() in {k.lower() for k in keys} or str(info.id) in keys


def _selected(info: ChatInfo, wanted: list[str]) -> bool:
    return True if not wanted else chat_matches(info, wanted)


async def fetch_messages() -> list[TgMessage]:
    """Tanlangan kanal/guruhlardan so'nggi xabarlarni o'qiydi."""
    client = await get_client()
    wanted = settings.tg_chats_list
    out: list[TgMessage] = []
    async for d in client.iter_dialogs(limit=settings.tg_dialog_limit):
        info = _chat_info(d)
        if info is None or not _selected(info, wanted):
            continue
        try:
            async for m in client.iter_messages(d.entity, limit=settings.tg_messages_per_chat):
                if m.message:
                    out.append(TgMessage(info, m.id, m.message, m.date))
        except Exception:
            continue  # ruxsat yo'q / flood-wait — shu chatni o'tkazib yuboramiz
    return out
