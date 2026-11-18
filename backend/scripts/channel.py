"""Telegram kanal(lar)ini boshqarish (admin "Kanal" bo'limi tayyor bo'lguncha). Token hech qachon chiqarilmaydi.

    docker-compose exec backend python scripts/channel.py status              # bot, kanallar, postlar soni
    docker-compose exec backend python scripts/channel.py chats               # bot qo'shilgan chatlar (bot_chats)
    docker-compose exec backend python scripts/channel.py add --chat -100123 --name "Yangiliklar" --feed
    docker-compose exec backend python scripts/channel.py set 1 mode=auto     # dry_run | review | auto
    docker-compose exec backend python scripts/channel.py test 1              # sinov xabari (haqiqiy)
    docker-compose exec backend python scripts/channel.py preview 1 -n 3      # oxirgi tayyorlangan postlar matni
    docker-compose exec backend python scripts/channel.py pending             # tasdiq kutayotganlar
    docker-compose exec backend python scripts/channel.py approve 15 [16 ...] # → navbatga
    docker-compose exec backend python scripts/channel.py reject 15

`--feed` — yangiliklar lentasi: hamma hodisa (global ham), hamma band, brifing/hisobotlarsiz, kuniga 1000 tagacha,
tunda ovozsiz, faqat kanal tilida (`require_translation`). Har yangi kanal `dry_run` da boshlanadi.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models import BotChat, ChannelDestination, ChannelPost  # noqa: E402
from app.models.publisher import BANDS, LANGS, MODES, QUIET_POLICIES  # noqa: E402
from app.services.publisher.bot import BotError, make_client, redact, token_configured  # noqa: E402
from app.services.publisher.outbox import get_state, insert_post  # noqa: E402
from app.services.publisher.render import render_test  # noqa: E402
from app.services.publisher.sender import mark_down, mark_up  # noqa: E402
from app.services.publisher.updates import can_post  # noqa: E402

FEED = {
    "lang": "uz-Cyrl", "countries": [], "include_global": True, "categories": [], "instant_min_band": "low",
    "daily_enabled": False, "weekly_enabled": False, "quiet_enabled": True, "quiet_policy": "all_silent",
    "max_instant_per_day": 1000, "show_original": False, "explain_terms": False, "require_translation": True,
}
SETTABLE = {
    "name": str, "mode": MODES, "lang": LANGS, "is_test": bool, "include_global": bool, "instant_min_band": BANDS,
    "quiet_enabled": bool, "quiet_policy": QUIET_POLICIES, "max_instant_per_day": int, "protect_content": bool,
    "show_original": bool, "require_translation": bool, "enabled": bool, "paused": bool, "topic_id": int,
    "countries": list, "categories": list,
}


def _parse(field: str, raw: str):
    kind = SETTABLE[field]
    if kind is bool:
        if raw.lower() not in ("true", "false", "1", "0", "yes", "no"):
            raise SystemExit(f"{field}: true / false kutilgan")
        return raw.lower() in ("true", "1", "yes")
    if kind is int:
        return int(raw)
    if kind is list:
        return [x.strip() for x in raw.split(",") if x.strip()]
    if isinstance(kind, tuple):
        if raw not in kind:
            raise SystemExit(f"{field}: {', '.join(kind)} dan biri")
        return raw
    return raw


async def _dest(db, ident: str) -> ChannelDestination:
    d = await db.get(ChannelDestination, int(ident)) if ident.isdigit() else await db.scalar(
        select(ChannelDestination).where(ChannelDestination.name == ident))
    if d is None:
        raise SystemExit(f"Kanal topilmadi: {ident}")
    return d


async def cmd_status(_args) -> None:
    async with AsyncSessionLocal() as db:
        st = await get_state(db)
        print(f"Bot: {st.bot_status} @{st.bot_username or '-'} (token {'bor' if token_configured() else 'YOQ'}); "
              f"oxirgi poll: {st.last_poll_at or '-'}; pauza: {st.paused}")
        for d in (await db.scalars(select(ChannelDestination).order_by(ChannelDestination.id))).all():
            counts = dict((await db.execute(select(ChannelPost.status, func.count()).where(
                ChannelPost.destination_id == d.id).group_by(ChannelPost.status))).all())
            print(f"[{d.id}] {d.name}: chat={d.chat_id} «{d.chat_title or '-'}» mode={d.mode} lang={d.lang} "
                  f"holat={d.status} enabled={d.enabled} paused={d.paused} test={d.is_test}")
            print(f"     postlar: {counts or '-'}" + (f"; xato: {d.last_error}" if d.last_error else ""))
        await db.commit()


async def cmd_chats(_args) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(select(BotChat).order_by(BotChat.updated_at.desc()))).all()
        if not rows:
            print("Hali chat yo'q: botni kanalga admin qiling (backend ishlab turganda yangilanish keladi).")
        for c in rows:
            ok = can_post(c.type, c.status, c.rights or {})
            print(f"{c.chat_id}  {c.type:<10} {c.status:<13} post={'ha' if ok else 'yoq'}  «{c.title or '-'}»"
                  f"{' @' + c.username if c.username else ''}  (qo'shgan: {c.added_by_name or '-'})")


async def cmd_add(args) -> None:
    async with AsyncSessionLocal() as db:
        chat = await db.get(BotChat, int(args.chat)) if args.chat else None
        if args.chat and chat is None:
            raise SystemExit("Bu chat bot_chats da yo'q — avval botni kanalga admin qiling, keyin `chats`")
        d = ChannelDestination(name=args.name, chat_id=chat.chat_id if chat else None,
                               chat_title=chat.title if chat else None, chat_type=chat.type if chat else None,
                               chat_username=chat.username if chat else None, rights=(chat.rights if chat else {}),
                               mode="dry_run", is_test=args.test, enabled_at=datetime.now(UTC))
        for k, v in (FEED if args.feed else {}).items():
            setattr(d, k, v)
        if args.lang:
            d.lang = args.lang
        if chat is not None:
            d.status = "ok" if can_post(chat.type, chat.status, chat.rights or {}) else "down"
        db.add(d)
        await db.commit()
        print(f"Qo'shildi: [{d.id}] {d.name} (mode=dry_run, lang={d.lang}). Tekshirish: preview {d.id}; "
              f"yoqish: set {d.id} mode=auto")


async def cmd_set(args) -> None:
    async with AsyncSessionLocal() as db:
        d = await _dest(db, args.id)
        for pair in args.pairs:
            field, _, raw = pair.partition("=")
            if field == "chat":  # chatni keyin bog'lash (bot kanalga qo'shilgandan so'ng)
                chat = await db.get(BotChat, int(raw))
                if chat is None:
                    raise SystemExit("Bu chat bot_chats da yo'q — `chats` ro'yxatini ko'ring")
                d.chat_id, d.chat_title, d.chat_type, d.chat_username = chat.chat_id, chat.title, chat.type, chat.username
                d.rights = chat.rights or {}
                d.status = "ok" if can_post(chat.type, chat.status, chat.rights or {}) else "down"
                continue
            if field not in SETTABLE:
                raise SystemExit(f"O'zgartirib bo'lmaydi: {field}. Mumkin: {', '.join(SETTABLE)}")
            setattr(d, field, _parse(field, raw))
            if field == "enabled" and d.enabled:
                d.enabled_at = datetime.now(UTC)  # qayta yoqish eski hodisalar bilan to'ldirmaydi
        await db.commit()
        print(f"[{d.id}] {d.name}: mode={d.mode} lang={d.lang} enabled={d.enabled} paused={d.paused}")


async def cmd_test(args) -> None:
    async with AsyncSessionLocal() as db:
        d = await _dest(db, args.id)
        if d.chat_id is None:
            raise SystemExit("Kanalga chat bog'lanmagan")
        now = datetime.now(UTC)
        text = render_test(d.lang, now)
        post = await insert_post(db, destination_id=d.id, kind="test", dedup_key=f"test:{now.timestamp():.0f}",
                                 status="sending", lang=d.lang, text=text)
        await db.commit()
        client = make_client()
        try:
            msg = await client.send_message(d.chat_id, text, thread_id=d.topic_id)
            post.status, post.message_id, post.chat_id, post.sent_at = "sent", msg.message_id, msg.chat_id, now
            await mark_up(db, d, now)
            print(f"Yuborildi: message_id={msg.message_id}")
        except BotError as exc:
            post.status, post.last_error = "failed", redact(str(exc))[:500]
            await mark_down(db, d, post.last_error, now)
            print(f"Xato: {post.last_error}")
        finally:
            await client.aclose()
            await db.commit()


async def cmd_preview(args) -> None:
    async with AsyncSessionLocal() as db:
        d = await _dest(db, args.id)
        rows = (await db.scalars(select(ChannelPost).where(ChannelPost.destination_id == d.id, ChannelPost.text != "")
                                 .order_by(ChannelPost.id.desc()).limit(args.n))).all()
        for p in reversed(rows):
            print(f"──── post {p.id} · {p.status}{' / ' + p.skip_reason if p.skip_reason else ''} · "
                  f"{len(p.final_text)} belgi · tugmalar: {[b['text'] for r in p.buttons for b in r]}")
            print(p.final_text)
        if not rows:
            print("Hali post yo'q (rejalashtiruvchi har 30 s da ishlaydi; tarjima tayyor bo'lishini kutadi).")


async def cmd_pending(_args) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(select(ChannelPost).where(ChannelPost.status == "awaiting_approval")
                                 .order_by(ChannelPost.id))).all()
        for p in rows:
            first = p.final_text.splitlines()[1] if p.final_text.count("\n") else p.final_text
            print(f"{p.id}  kanal={p.destination_id}  {first[:110]}")
        print(f"Jami: {len(rows)}")


async def cmd_decide(args, status: str) -> None:
    async with AsyncSessionLocal() as db:
        for pid in args.ids:
            p = await db.get(ChannelPost, int(pid))
            if p is None or p.status != "awaiting_approval":
                print(f"{pid}: tasdiq kutmayapti")
                continue
            p.status, p.approved_at, p.approved_by_name = status, datetime.now(UTC), "cli"
            print(f"{pid}: {status}")
        await db.commit()


def main() -> None:
    ap = argparse.ArgumentParser(description="Telegram kanal(lar)i")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("chats")
    a = sub.add_parser("add")
    a.add_argument("--chat", help="chat_id (`chats` ro'yxatidan)")
    a.add_argument("--name", required=True)
    a.add_argument("--lang", choices=LANGS)
    a.add_argument("--feed", action="store_true", help="yangiliklar lentasi sozlamalari")
    a.add_argument("--test", action="store_true", help="sinov kanali")
    s = sub.add_parser("set")
    s.add_argument("id")
    s.add_argument("pairs", nargs="+", metavar="maydon=qiymat")
    t_ = sub.add_parser("test")
    t_.add_argument("id")
    p = sub.add_parser("preview")
    p.add_argument("id")
    p.add_argument("-n", type=int, default=5)
    sub.add_parser("pending")
    for name in ("approve", "reject"):
        x = sub.add_parser(name)
        x.add_argument("ids", nargs="+")
    args = ap.parse_args()
    handlers = {"status": cmd_status, "chats": cmd_chats, "add": cmd_add, "set": cmd_set, "test": cmd_test,
                "preview": cmd_preview, "pending": cmd_pending,
                "approve": lambda a: cmd_decide(a, "queued"), "reject": lambda a: cmd_decide(a, "rejected")}
    asyncio.run(handlers[args.cmd](args))


if __name__ == "__main__":
    main()
