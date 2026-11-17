from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession
from app.core import ratelimit
from app.core.config import settings
from app.core.errors import api_error
from app.core.i18n import current_lang, t
from app.models import Source
from app.services import telegram_user as tg
from app.services.events.telegram_archive import is_monitored, monitored_keys

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class TgStatus(BaseModel):
    configured: bool  # api_id/hash bormi
    session: bool  # session fayli bormi
    authorized: bool  # login qilinganmi
    account: str | None = None
    chats_filter: list[str]  # .env TG_CHATS (boshlang'ich seed) — kuzatilayotganlar emas
    uz_filter: bool
    message: str
    # Haqiqatda kuzatilayotganlar: yoqilgan `telegram_user` manbalari va ulardan global (kiber filtri) bo'lganlari
    sources: int = 0
    global_sources: int = 0


class TgChat(BaseModel):
    id: int
    title: str
    username: str | None
    kind: str
    archived: bool = False  # Telegram "Arxiv" papkasida
    monitored: bool = False  # bu chat uchun `telegram_user` manbasi allaqachon bor


@router.get("/status", response_model=TgStatus)
async def tg_status(current_user: AdminUser, db: DbSession) -> TgStatus:
    enabled_tg = (Source.kind == "telegram_user") & Source.enabled
    counts = (await db.execute(select(
        func.count(Source.id), func.count(Source.id).filter(Source.scope == "global")
    ).where(enabled_tg))).one()
    base = dict(
        configured=tg.is_configured(),
        session=tg.session_exists(),
        chats_filter=settings.tg_chats_list,
        uz_filter=settings.tg_uz_filter,
        sources=counts[0],
        global_sources=counts[1],
    )
    if not base["configured"]:
        return TgStatus(**base, authorized=False,
                        message=t("tg_env_missing", current_lang()))
    try:
        client = await tg.get_client()
        me = await client.get_me()
        return TgStatus(**base, authorized=True,
                        account=" ".join(
                            x for x in [me.first_name, me.last_name,
                                        f"(@{me.username})" if me.username else None] if x
                        ) or str(me.id),
                        message=t("tg_connected", current_lang()))
    except tg.TelegramNotConfigured as exc:
        return TgStatus(**base, authorized=False, message=str(exc))


@router.get("/chats", response_model=list[TgChat])
async def tg_chats(current_user: AdminUser, db: DbSession, refresh: bool = False) -> list[TgChat]:
    """Admin chat tanlash ro'yxati: akkauntdagi BARCHA kanal/guruhlar (yig'uvchining `TG_DIALOG_LIMIT` chegarasi emas),
    5 daqiqa keshlanadi (`refresh=true` — qayta o'qish)."""
    if refresh:  # to'liq qayta o'qish — bir necha GetDialogs so'rovi
        ratelimit.check("tg-chats", str(current_user.id), settings.refresh_rate, settings.refresh_rate_window)
    try:
        chats = await tg.list_chats(full=True, refresh=refresh)
    except tg.TelegramNotConfigured as exc:
        raise api_error(status.HTTP_409_CONFLICT, "telegram_not_configured", message=str(exc)) from exc
    known = await monitored_keys(db)
    return [TgChat(id=c.id, title=c.title, username=c.username, kind=c.kind, archived=c.archived,
                   monitored=is_monitored(c, known)) for c in chats]
