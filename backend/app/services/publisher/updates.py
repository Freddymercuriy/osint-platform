"""Bot yangilanishlari (long polling `getUpdates`; platformaning ochiq manzili yo'q — webhook ishlamaydi).

- `my_chat_member` → `bot_chats` (bot qo'shilgan / chiqarilgan chat, huquqlari). Kanal manziliga bog'langan chatda
  bot chiqarilsa yoki post huquqini yo'qotsa — kanal darhol `down`; qayta admin qilinsa — `ok`.
- Shaxsiy chatda `/start` — foydalanuvchiga Telegram ID'sini va tasdiqlovchi bo'lish yo'lini aytadi.
- `callback_query` — Telegram orqali tasdiqlash hali yo'q: "yoqilmagan" deb javob.
Offset bazada (`publisher_state.updates_offset`) — restartdan keyin yangilanishlar qayta ishlanmaydi.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import t
from app.models import BotChat, ChannelDestination
from app.services.publisher.bot import BotClient, BotError
from app.services.publisher.outbox import get_state
from app.services.publisher.sender import mark_down, mark_up

log = logging.getLogger("osint.publisher")

ALLOWED = ["my_chat_member", "message", "callback_query"]
RIGHT_KEYS = ("can_post_messages", "can_edit_messages", "can_delete_messages", "can_manage_chat",
              "can_invite_users", "can_pin_messages")


def can_post(chat_type: str, status: str, rights: dict) -> bool:
    if status == "creator":
        return True
    if chat_type == "channel":
        return status == "administrator" and bool(rights.get("can_post_messages"))
    return status in ("administrator", "member", "restricted") and rights.get("can_send_messages", True) is not False


def _user_lang(user: dict) -> str:
    code = (user.get("language_code") or "").lower()
    return "ru" if code.startswith("ru") else "en" if code.startswith("en") else "uz"


def _name(user: dict) -> str | None:
    value = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x).strip() or user.get("username")
    return str(value)[:128] if value else None


async def upsert_chat(db: AsyncSession, chat: dict, status: str, rights: dict, by: dict | None) -> None:
    values = {
        "chat_id": int(chat["id"]), "type": str(chat.get("type") or "unknown")[:16],
        "title": (chat.get("title") or _name(chat) or "")[:255] or None,
        "username": (chat.get("username") or None), "status": status[:16], "rights": rights,
        "added_by_tg_id": (by or {}).get("id"), "added_by_name": _name(by or {}),
    }
    update = {k: v for k, v in values.items() if k != "chat_id" and (v is not None or k in ("username",))}
    update["updated_at"] = datetime.now(UTC)
    await db.execute(insert(BotChat).values(**values).on_conflict_do_update(index_elements=["chat_id"], set_=update))


async def on_my_chat_member(db: AsyncSession, m: dict) -> None:
    chat, new = m.get("chat") or {}, m.get("new_chat_member") or {}
    if "id" not in chat:
        return
    status = str(new.get("status") or "unknown")
    rights = {k: bool(new[k]) for k in (*RIGHT_KEYS, "can_send_messages") if k in new}
    await upsert_chat(db, chat, status, rights, m.get("from"))
    now = datetime.now(UTC)
    for d in (await db.scalars(select(ChannelDestination).where(ChannelDestination.chat_id == int(chat["id"])))).all():
        d.chat_title = chat.get("title") or d.chat_title
        d.chat_username = chat.get("username")
        d.chat_type = chat.get("type") or d.chat_type
        d.rights, d.rights_checked_at = rights, now
        if can_post(d.chat_type or "", status, rights):
            await mark_up(db, d, now)
        else:
            await mark_down(db, d, f"bot holati: {status}, post huquqi yo'q", now)


async def on_message(db: AsyncSession, client: BotClient, msg: dict) -> None:
    chat, user = msg.get("chat") or {}, msg.get("from") or {}
    if chat.get("type") != "private" or not str(msg.get("text") or "").startswith("/start"):
        return
    await upsert_chat(db, chat, "private", {}, user)
    try:
        await client.send_message(chat["id"], t("pub_start_reply", _user_lang(user), id=user.get("id")),
                                  parse_mode=None)
    except BotError as exc:
        log.warning("/start javobi yuborilmadi: %s", exc)


async def on_callback(client: BotClient, cq: dict) -> None:
    try:
        await client.answer_callback_query(cq["id"], t("pub_review_unavailable", _user_lang(cq.get("from") or {})))
    except BotError as exc:
        log.warning("callback javobi yuborilmadi: %s", exc)


async def poll_once(db: AsyncSession, client: BotClient, *, timeout: int = 25) -> int:
    st = await get_state(db)
    offset = st.updates_offset
    await db.commit()  # long poll paytida ulanish band turmasin
    updates = await client.get_updates(offset, timeout=timeout, allowed_updates=ALLOWED)
    st = await get_state(db)
    for u in updates:
        try:
            if "my_chat_member" in u:
                await on_my_chat_member(db, u["my_chat_member"])
            elif "message" in u:
                await on_message(db, client, u["message"])
            elif "callback_query" in u:
                await on_callback(client, u["callback_query"])
        except Exception:
            log.exception("Yangilanish %s ni qayta ishlashda xato", u.get("update_id"))
        st.updates_offset = int(u["update_id"]) + 1
    st.last_poll_at = datetime.now(UTC)
    await db.commit()
    return len(updates)
