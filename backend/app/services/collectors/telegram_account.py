"""Telegram akkaunti bo'yicha qidiruv (username yoki ID) — foydalanuvchining o'z akkaunti orqali.

Nima ko'rsatiladi (faqat Telegram'ning o'zi har qanday foydalanuvchiga ko'rsatadigan narsalar):
  - akkaunt: ID, tur (foydalanuvchi / bot / kanal / guruh), ochiq ism, belgilar (premium, scam ...);
  - faol usernamelar, bio, shaxsiy kanal;
  - username tarixi — platformaning O'Z kuzatuv jurnali (`tg_observations`): Telegram o'tgan
    o'zgarishlarni bermaydi, shuning uchun har qidiruvda joriy holat yoziladi va o'zgarish
    ikki kuzatuv oralig'i aniqligida chiqadi;
  - umumiy guruhlar (sizning akkauntingiz ham a'zo bo'lganlari) va ularda shu akkaunt yozgan
    xabarlar soni, birinchi/oxirgi sanasi.

Nima QILINMAYDI: telefon raqami va "oxirgi marta ko'rilgan" holati o'qilmaydi; boshqa odamning
barcha guruhlari ro'yxati olinmaydi (Telegram bermaydi); sizib chiqqan / uchinchi tomon
kuzatuv bazalari ishlatilmaydi. Jurnalga faqat ID, tur va usernamelar yoziladi.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import errors, functions, types

from app.models import TgObservation
from app.services import telegram_user as tg
from app.services.collectors.base import BaseCollector, CollectResult

_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
_LINK_RE = re.compile(r"^(?:https?://)?(?:t|telegram)\.me/(?:s/)?([A-Za-z0-9_]+)/?(?:\?.*)?$", re.I)
_ID_RE = re.compile(r"^(?:id)?\s*(-?\d{5,16})$", re.I)

_MAX_COMMON = 100  # Telegram bir so'rovda beradigan umumiy chatlar soni
_MAX_COUNTED = 15  # nechta guruhda xabarlar sanaladi (flood-wait'dan saqlanish)
_TASHKENT = timezone(timedelta(hours=5))
_MONTHS = ("yan", "fev", "mar", "apr", "may", "iyun", "iyul", "avg", "sen", "okt", "noy", "dek")


def parse_query(query: str) -> tuple[str, str | int]:
    """→ ("username", "durov") yoki ("id", 123456). Yaroqsiz bo'lsa ValueError."""
    q = (query or "").strip()
    if m := _ID_RE.match(q):
        raw = m.group(1).lstrip("-")
        if raw.startswith("100") and len(raw) > 10:  # -100xxxxxxxxxx — kanal/superguruh shakli
            raw = raw[3:]
        return "id", int(raw)
    if m := _LINK_RE.match(q):
        q = m.group(1)
    q = q.lstrip("@")
    if not _USERNAME_RE.match(q):
        raise ValueError(
            "Telegram username (@nom yoki t.me/nom: 4–32 belgi, lotin harf, raqam, _) "
            "yoki raqamli ID kiriting"
        )
    return "username", q


def _fmt(dt: datetime | None) -> str:
    if dt is None:
        return "?"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    d = dt.astimezone(_TASHKENT)
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year} {d:%H:%M}"


def _usernames(ent) -> list[str]:
    """Faol usernamelar (asosiy + qo'shimcha), kichik harfda, takrorsiz."""
    names: list[str] = []
    if getattr(ent, "username", None):
        names.append(ent.username)
    for u in getattr(ent, "usernames", None) or []:
        if getattr(u, "active", True) and u.username:
            names.append(u.username)
    return sorted({n.lower() for n in names})


def _kind(ent) -> str:
    if isinstance(ent, types.User):
        return "bot" if ent.bot else "user"
    if isinstance(ent, types.Channel):
        return "group" if ent.megagroup else "channel"
    return "group"


_KIND_LABEL = {"user": "foydalanuvchi", "bot": "bot", "channel": "kanal", "group": "guruh"}


def _link(usernames: list[str]) -> str | None:
    return f"https://t.me/{usernames[0]}" if usernames else None


def _chat_link(chat) -> str | None:
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}"
    return None


class TelegramAccountCollector(BaseCollector):
    """Telegram akkaunti: ID, usernamelar, username tarixi (o'z jurnalimiz), umumiy guruhlar."""

    name = "telegram_account"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------ kuzatuv jurnali
    async def _history(self, tg_id: int) -> list[TgObservation]:
        rows = await self.db.scalars(
            select(TgObservation).where(TgObservation.tg_id == tg_id).order_by(TgObservation.id)
        )
        return list(rows)

    async def _observe(self, tg_id: int, kind: str, usernames: list[str]) -> list[TgObservation]:
        """Joriy holatni jurnalga yozadi va to'liq tarixni qaytaradi (commit — chaqiruvchida)."""
        now = datetime.now(UTC)
        joined = ",".join(usernames)[:512]
        history = await self._history(tg_id)
        if history and history[-1].usernames == joined:
            history[-1].last_seen = now
        else:
            row = TgObservation(
                tg_id=tg_id, kind=kind, usernames=joined, first_seen=now, last_seen=now
            )
            self.db.add(row)
            history.append(row)
        await self.db.flush()
        return history

    async def _last_known(self, tg_id: int) -> list[str]:
        history = await self._history(tg_id)
        for row in reversed(history):
            if row.usernames:
                return row.usernames.split(",")
        return []

    async def _previous_owners(self, username: str, tg_id: int) -> list[TgObservation]:
        """Shu username jurnalda boshqa ID'ga tegishli bo'lgan kuzatuvlar."""
        rows = await self.db.scalars(
            select(TgObservation)
            .where(TgObservation.tg_id != tg_id, TgObservation.usernames.ilike(f"%{username}%"))
            .order_by(TgObservation.id)
        )
        return [r for r in rows if username.lower() in r.usernames.split(",")]

    # ------------------------------------------------------------ Telegram
    async def _resolve_username(self, client, username: str):
        """Username → entity. Telegram serveridan (kesh emas) — username boshqaga o'tgan
        bo'lsa ham to'g'ri egasini qaytaradi. Topilmasa None."""
        try:
            res = await client(functions.contacts.ResolveUsernameRequest(username))
        except (errors.UsernameNotOccupiedError, errors.UsernameInvalidError):
            return None
        for ent in list(res.users) + list(res.chats):
            if ent.id == getattr(res.peer, "user_id", None) or ent.id == getattr(
                res.peer, "channel_id", getattr(res.peer, "chat_id", None)
            ):
                return ent
        return None

    async def _resolve_id(self, client, tg_id: int):
        """ID → entity. Telegram ID bo'yicha faqat akkauntingiz avval "ko'rgan" obyektni ochadi
        (sessiya keshidagi access_hash). Topilmasa None."""
        for peer in (types.PeerUser(tg_id), types.PeerChannel(tg_id), types.PeerChat(tg_id)):
            try:
                return await client.get_entity(await client.get_input_entity(peer))
            except (ValueError, TypeError, errors.RPCError):
                continue
        return None

    async def _activity(self, client, chat, user) -> str:
        """Guruhda shu akkaunt yozgan xabarlar: soni va birinchi/oxirgi sanasi."""
        try:
            last = await client.get_messages(chat, from_user=user, limit=1)
            total = getattr(last, "total", 0) or 0
            if not total:
                return "bu akkauntdan xabar topilmadi"
            first = await client.get_messages(chat, from_user=user, limit=1, reverse=True)
            first_date = first[0].date if first else None
            last_date = last[0].date if last else None
            return f"xabarlar: {total} (birinchi: {_fmt(first_date)}, oxirgi: {_fmt(last_date)})"
        except errors.FloodWaitError as exc:
            return f"xabarlar sanalmadi (Telegram cheklovi, {exc.seconds} s)"
        except Exception:
            return "xabarlar sanalmadi (ruxsat yo'q)"

    # ------------------------------------------------------------ natija qatorlari
    def _history_rows(self, history: list[TgObservation]) -> CollectResult:
        def names(row: TgObservation) -> str:
            return ", ".join(f"@{u}" for u in row.usernames.split(",")) if row.usernames else "username yo'q"

        if len(history) < 2:
            return CollectResult(
                source="Username tarixi",
                type="history",
                value="O'zgarish qayd etilmagan",
                status="not_found",
                detail=(
                    f"Kuzatuv boshlangan: {_fmt(history[0].first_seen)}. Telegram o'tgan "
                    "o'zgarishlarni bermaydi — platforma har qidiruvda holatni yozib boradi; "
                    "username o'zgarsa, keyingi qidiruvda (ID bo'yicha ham) shu yerda chiqadi."
                ),
            )
        steps = []
        for prev, cur in zip(history, history[1:]):
            steps.append(
                f"{names(prev)} → {names(cur)}: {_fmt(prev.last_seen)} va {_fmt(cur.first_seen)} oralig'ida"
            )
        return CollectResult(
            source="Username tarixi",
            type="history",
            value=f"{len(history) - 1} ta o'zgarish",
            status="found",
            detail=(
                " · ".join(reversed(steps))
                + f" · Kuzatuv boshlangan: {_fmt(history[0].first_seen)} ({names(history[0])})"
            ),
        )

    async def _common_rows(self, client, user) -> list[CollectResult]:
        try:
            res = await client(
                functions.messages.GetCommonChatsRequest(user_id=user, max_id=0, limit=_MAX_COMMON)
            )
        except errors.FloodWaitError as exc:
            return [CollectResult(
                source="Umumiy guruhlar", type="groups", value="Tekshirilmadi", status="error",
                detail=f"Telegram so'rovlarni vaqtincha chekladi — {exc.seconds} soniyadan keyin urinib ko'ring.",
            )]
        except errors.RPCError as exc:
            return [CollectResult(
                source="Umumiy guruhlar", type="groups", value="Tekshirilmadi", status="error",
                detail=f"Telegram xatosi: {type(exc).__name__}",
            )]
        chats = list(res.chats)
        if not chats:
            return [CollectResult(
                source="Umumiy guruhlar", type="groups", value="Yo'q", status="not_found",
                detail=(
                    "Sizning Telegram akkauntingiz a'zo bo'lgan guruhlarning hech birida bu akkaunt "
                    "yo'q. Telegram faqat umumiy guruhlarni ko'rsatadi — boshqa guruhlari ko'rinmaydi."
                ),
            )]
        rows: list[CollectResult] = []
        for n, chat in enumerate(chats):
            members = getattr(chat, "participants_count", None)
            parts = ["Umumiy guruh" + (" (ochiq)" if getattr(chat, "username", None) else " (yopiq)")]
            if members:
                parts.append(f"a'zolar: {members}")
            if n < _MAX_COUNTED:
                parts.append(await self._activity(client, chat, user))
            rows.append(CollectResult(
                source=f"Guruh: {chat.title}",
                type="group",
                value=f"ID {chat.id}",
                url=_chat_link(chat),
                detail=" · ".join(parts),
                status="found",
            ))
        return rows

    # ------------------------------------------------------------ asosiy
    async def run(self, query: str) -> list[CollectResult]:
        mode, target = parse_query(query)
        try:
            client = await tg.get_client()
        except tg.TelegramNotConfigured as exc:
            return [CollectResult(
                source="Telegram", type="account", value=str(target), status="error",
                detail=f"Telegram akkaunti ulanmagan: {exc}",
            )]

        results: list[CollectResult] = []
        try:
            if mode == "username":
                ent = await self._resolve_username(client, str(target))
                if ent is None:
                    return [CollectResult(
                        source="Telegram akkaunt", type="account", value=f"@{target}",
                        url=f"https://t.me/{target}", status="not_found",
                        detail="Bu username hozir hech kimga tegishli emas (bo'sh yoki o'zgartirilgan).",
                    )] + await self._orphan_rows(str(target))
            else:
                ent = await self._resolve_id(client, int(target))
                known = await self._last_known(int(target))
                if ent is None and known:
                    # Avval shu ID bilan ko'rilgan username orqali urinib ko'ramiz
                    cand = await self._resolve_username(client, known[0])
                    if cand is not None and cand.id == int(target):
                        ent = cand
                    elif cand is not None:
                        results.append(CollectResult(
                            source="Username boshqa akkauntda", type="history",
                            value=f"@{known[0]} → ID {cand.id}", url=f"https://t.me/{known[0]}",
                            status="found",
                            detail=(
                                f"ID {target} avval @{known[0]} bilan ko'rilgan edi; hozir bu username "
                                f"boshqa akkauntga (ID {cand.id}) tegishli — egasi usernameni o'zgartirgan."
                            ),
                        ))
                if ent is None:
                    return results + [CollectResult(
                        source="Telegram akkaunt", type="account", value=f"ID {target}",
                        status="error",
                        detail=(
                            "Bu ID'ni ochib bo'lmadi. Telegram ID bo'yicha faqat akkauntingiz avval "
                            "ko'rgan (umumiy guruhda uchragan yoki username orqali qidirilgan) "
                            "akkauntlarni ochadi. Username bilan bir marta qidiring — keyin ID ishlaydi."
                        ),
                    )]
        except errors.FloodWaitError as exc:
            return [CollectResult(
                source="Telegram", type="account", value=str(target), status="error",
                detail=f"Telegram so'rovlarni vaqtincha chekladi — {exc.seconds} soniyadan keyin urinib ko'ring.",
            )]

        usernames = _usernames(ent)
        kind = _kind(ent)
        url = _link(usernames)

        # --- akkaunt ---
        if isinstance(ent, types.User):
            name = " ".join(p for p in (ent.first_name, ent.last_name) if p) or "—"
            flags = [
                label for label, on in (
                    ("o'chirilgan akkaunt", ent.deleted), ("tasdiqlangan", ent.verified),
                    ("Premium", ent.premium), ("SCAM belgisi", ent.scam), ("FAKE belgisi", ent.fake),
                    ("cheklangan", ent.restricted), ("kontaktlaringizda", ent.contact),
                ) if on
            ]
            detail = f"Tur: {_KIND_LABEL[kind]} · Ism: {name}"
        else:
            flags = [
                label for label, on in (
                    ("tasdiqlangan", getattr(ent, "verified", False)),
                    ("SCAM belgisi", getattr(ent, "scam", False)),
                    ("FAKE belgisi", getattr(ent, "fake", False)),
                ) if on
            ]
            detail = f"Tur: {_KIND_LABEL[kind]} · Nomi: {getattr(ent, 'title', '—')}"
            if getattr(ent, "participants_count", None):
                detail += f" · a'zolar: {ent.participants_count}"
        if flags:
            detail += " · " + ", ".join(flags)
        results.append(CollectResult(
            source="Telegram akkaunt", type="account", value=f"ID {ent.id}", url=url,
            detail=detail, status="found",
        ))

        # --- usernamelar ---
        results.append(CollectResult(
            source="Username",
            type="username",
            value=", ".join(f"@{u}" for u in usernames) if usernames else "Username yo'q",
            url=url,
            status="found" if usernames else "not_found",
            detail=(
                f"Faol usernamelar: {len(usernames)}" if usernames
                else "Akkauntda hozir ochiq username yo'q (o'chirilgan yoki umuman qo'yilmagan)."
            ),
        ))

        # --- bio / tavsif, shaxsiy kanal ---
        about, personal = await self._about(client, ent)
        if about:
            results.append(CollectResult(
                source="Bio" if isinstance(ent, types.User) else "Tavsif",
                type="bio", value=about, detail=about, status="found",
            ))
        if personal is not None:
            results.append(CollectResult(
                source="Shaxsiy kanal", type="channel", value=personal.title,
                url=_chat_link(personal), status="found",
                detail=f"ID {personal.id} · profilida ko'rsatilgan kanal",
            ))

        # --- username tarixi (o'z jurnalimiz) ---
        history = await self._observe(ent.id, kind, usernames)
        results.append(self._history_rows(history))
        for u in usernames:
            for row in await self._previous_owners(u, ent.id):
                results.append(CollectResult(
                    source="Username avvalgi egasi", type="history",
                    value=f"@{u} — ID {row.tg_id}", status="found",
                    detail=(
                        f"@{u} {_fmt(row.first_seen)} – {_fmt(row.last_seen)} oralig'ida boshqa "
                        f"akkauntda (ID {row.tg_id}) ko'rilgan."
                    ),
                ))

        # --- umumiy guruhlar ---
        if isinstance(ent, types.User) and not ent.is_self:
            results.extend(await self._common_rows(client, ent))
        return results

    async def _about(self, client, ent):
        """(bio/tavsif, shaxsiy kanal | None). Xato bo'lsa bo'sh."""
        try:
            if isinstance(ent, types.User):
                full = await client(functions.users.GetFullUserRequest(ent))
                pid = full.full_user.personal_channel_id
                personal = next((c for c in full.chats if c.id == pid), None) if pid else None
                return (full.full_user.about or "").strip(), personal
            if isinstance(ent, types.Channel):
                full = await client(functions.channels.GetFullChannelRequest(ent))
                if full.full_chat.participants_count and not getattr(ent, "participants_count", None):
                    ent.participants_count = full.full_chat.participants_count
                return (full.full_chat.about or "").strip(), None
        except errors.RPCError:
            pass
        return "", None

    async def _orphan_rows(self, username: str) -> list[CollectResult]:
        """Bo'sh username jurnalda avval kimga tegishli bo'lgani."""
        rows = await self._previous_owners(username, tg_id=0)
        return [
            CollectResult(
                source="Username avvalgi egasi", type="history",
                value=f"@{username} — ID {r.tg_id}", status="found",
                detail=(
                    f"@{username} {_fmt(r.first_seen)} – {_fmt(r.last_seen)} oralig'ida ID {r.tg_id} "
                    "akkauntida ko'rilgan. Shu ID bo'yicha qidirsangiz, joriy usernamesi chiqadi."
                ),
            )
            for r in rows
        ]
