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

from app.core.i18n import CodedValueError, current_lang, t
from app.models import TgObservation
from app.services import telegram_user as tg
from app.services.collectors.base import BaseCollector, CollectResult

_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
_LINK_RE = re.compile(r"^(?:https?://)?(?:t|telegram)\.me/(?:s/)?([A-Za-z0-9_]+)/?(?:\?.*)?$", re.I)
_ID_RE = re.compile(r"^(?:id)?\s*(-?\d{5,16})$", re.I)

_MAX_COMMON = 100  # Telegram bir so'rovda beradigan umumiy chatlar soni
_MAX_COUNTED = 15  # nechta guruhda xabarlar sanaladi (flood-wait'dan saqlanish)
_TASHKENT = timezone(timedelta(hours=5))


def _t(code: str, **params) -> str:
    """Joriy so'rov tilidagi matn (contextvar)."""
    return t(code, current_lang(), **params)


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
        raise CodedValueError("invalid_telegram_query")
    return "username", q


def _fmt(dt: datetime | None) -> str:
    if dt is None:
        return "?"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    d = dt.astimezone(_TASHKENT)
    months = t("tg_months", current_lang()).split(",")
    return f"{d.day} {months[d.month - 1]} {d.year} {d:%H:%M}"


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



def _kind_label(kind: str) -> str:
    return _t(f"tg_kind_{kind}")


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
                return _t("tg_act_none")
            first = await client.get_messages(chat, from_user=user, limit=1, reverse=True)
            first_date = first[0].date if first else None
            last_date = last[0].date if last else None
            return _t("tg_act_counts", total=total, first=_fmt(first_date), last=_fmt(last_date))
        except errors.FloodWaitError as exc:
            return _t("tg_act_flood", seconds=exc.seconds)
        except Exception:
            return _t("tg_act_denied")

    # ------------------------------------------------------------ natija qatorlari
    def _history_rows(self, history: list[TgObservation]) -> CollectResult:
        def names(row: TgObservation) -> str:
            return ", ".join(f"@{u}" for u in row.usernames.split(",")) if row.usernames else _t("tg_hist_no_username")

        if len(history) < 2:
            return CollectResult(
                source=_t("tg_src_history"),
                type="history",
                value=_t("tg_hist_none_value"),
                status="not_found",
                detail=_t("tg_hist_none_detail", since=_fmt(history[0].first_seen)),
            )
        steps = []
        for prev, cur in zip(history, history[1:]):
            steps.append(
                _t("tg_hist_step", prev=names(prev), cur=names(cur), a=_fmt(prev.last_seen), b=_fmt(cur.first_seen))
            )
        return CollectResult(
            source=_t("tg_src_history"),
            type="history",
            value=_t("tg_hist_count", n=len(history) - 1),
            status="found",
            detail=(
                " · ".join(reversed(steps))
                + " · " + _t("tg_hist_since", since=_fmt(history[0].first_seen), names=names(history[0]))
            ),
        )

    async def _common_rows(self, client, user) -> list[CollectResult]:
        try:
            res = await client(
                functions.messages.GetCommonChatsRequest(user_id=user, max_id=0, limit=_MAX_COMMON)
            )
        except errors.FloodWaitError as exc:
            return [CollectResult(
                source=_t("tg_src_common"), type="groups", value=_t("tg_not_checked"), status="error",
                detail=_t("tg_flood", seconds=exc.seconds),
            )]
        except errors.RPCError as exc:
            return [CollectResult(
                source=_t("tg_src_common"), type="groups", value=_t("tg_not_checked"), status="error",
                detail=_t("tg_rpc_error", name=type(exc).__name__),
            )]
        chats = list(res.chats)
        if not chats:
            return [CollectResult(
                source=_t("tg_src_common"), type="groups", value=_t("tg_common_none_value"), status="not_found",
                detail=_t("tg_common_none_detail"),
            )]
        rows: list[CollectResult] = []
        for n, chat in enumerate(chats):
            members = getattr(chat, "participants_count", None)
            parts = [_t("tg_common_group") + _t("tg_public" if getattr(chat, "username", None) else "tg_private")]
            if members:
                parts.append(_t("tg_members", n=members))
            if n < _MAX_COUNTED:
                parts.append(await self._activity(client, chat, user))
            rows.append(CollectResult(
                source=_t("tg_group_src", title=chat.title),
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
                detail=_t("tg_not_connected", error=exc),
            )]

        results: list[CollectResult] = []
        try:
            if mode == "username":
                ent = await self._resolve_username(client, str(target))
                if ent is None:
                    return [CollectResult(
                        source=_t("tg_src_account"), type="account", value=f"@{target}",
                        url=f"https://t.me/{target}", status="not_found",
                        detail=_t("tg_username_free"),
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
                            source=_t("tg_src_moved"), type="history",
                            value=f"@{known[0]} → ID {cand.id}", url=f"https://t.me/{known[0]}",
                            status="found",
                            detail=_t("tg_moved_detail", id=target, name=known[0], new_id=cand.id),
                        ))
                if ent is None:
                    return results + [CollectResult(
                        source=_t("tg_src_account"), type="account", value=f"ID {target}",
                        status="error",
                        detail=_t("tg_id_unresolved"),
                    )]
        except errors.FloodWaitError as exc:
            return [CollectResult(
                source="Telegram", type="account", value=str(target), status="error",
                detail=_t("tg_flood", seconds=exc.seconds),
            )]

        usernames = _usernames(ent)
        kind = _kind(ent)
        url = _link(usernames)

        # --- akkaunt ---
        if isinstance(ent, types.User):
            name = " ".join(p for p in (ent.first_name, ent.last_name) if p) or "—"
            flags = [
                label for label, on in (
                    (_t("tg_flag_deleted"), ent.deleted), (_t("tg_flag_verified"), ent.verified),
                    (_t("tg_flag_premium"), ent.premium), (_t("tg_flag_scam"), ent.scam),
                    (_t("tg_flag_fake"), ent.fake),
                    (_t("tg_flag_restricted"), ent.restricted), (_t("tg_flag_contact"), ent.contact),
                ) if on
            ]
            detail = _t("tg_detail_user", kind=_kind_label(kind), name=name)
        else:
            flags = [
                label for label, on in (
                    (_t("tg_flag_verified"), getattr(ent, "verified", False)),
                    (_t("tg_flag_scam"), getattr(ent, "scam", False)),
                    (_t("tg_flag_fake"), getattr(ent, "fake", False)),
                ) if on
            ]
            detail = _t("tg_detail_chat", kind=_kind_label(kind), name=getattr(ent, "title", "—"))
            if getattr(ent, "participants_count", None):
                detail += " · " + _t("tg_members", n=ent.participants_count)
        if flags:
            detail += " · " + ", ".join(flags)
        results.append(CollectResult(
            source="Telegram akkaunt", type="account", value=f"ID {ent.id}", url=url,
            detail=detail, status="found",
        ))

        # --- usernamelar ---
        results.append(CollectResult(
            source=_t("tg_src_username"),
            type="username",
            value=", ".join(f"@{u}" for u in usernames) if usernames else _t("tg_no_username"),
            url=url,
            status="found" if usernames else "not_found",
            detail=(
                _t("tg_active_usernames", n=len(usernames)) if usernames
                else _t("tg_no_public_username")
            ),
        ))

        # --- bio / tavsif, shaxsiy kanal ---
        about, personal = await self._about(client, ent)
        if about:
            results.append(CollectResult(
                source=_t("tg_src_bio" if isinstance(ent, types.User) else "tg_src_about"),
                type="bio", value=about, detail=about, status="found",
            ))
        if personal is not None:
            results.append(CollectResult(
                source=_t("tg_src_personal_channel"), type="channel", value=personal.title,
                url=_chat_link(personal), status="found",
                detail=_t("tg_personal_channel_detail", id=personal.id),
            ))

        # --- username tarixi (o'z jurnalimiz) ---
        history = await self._observe(ent.id, kind, usernames)
        results.append(self._history_rows(history))
        for u in usernames:
            for row in await self._previous_owners(u, ent.id):
                results.append(CollectResult(
                    source=_t("tg_src_prev_owner"), type="history",
                    value=f"@{u} — ID {row.tg_id}", status="found",
                    detail=_t("tg_prev_owner_detail", name=u, first=_fmt(row.first_seen), last=_fmt(row.last_seen), id=row.tg_id),
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
                source=_t("tg_src_prev_owner"), type="history",
                value=f"@{username} — ID {r.tg_id}", status="found",
                detail=_t("tg_orphan_detail", name=username, first=_fmt(r.first_seen), last=_fmt(r.last_seen), id=r.tg_id),
            )
            for r in rows
        ]
