from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.config import settings
from app.services import telegram_user as tg

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class TgStatus(BaseModel):
    configured: bool  # api_id/hash bormi
    session: bool  # session fayli bormi
    authorized: bool  # login qilinganmi
    account: str | None = None
    chats_filter: list[str]
    uz_filter: bool
    message: str


class TgChat(BaseModel):
    id: int
    title: str
    username: str | None
    kind: str


@router.get("/status", response_model=TgStatus)
async def tg_status(current_user: CurrentUser) -> TgStatus:
    base = dict(
        configured=tg.is_configured(),
        session=tg.session_exists(),
        chats_filter=settings.tg_chats_list,
        uz_filter=settings.tg_uz_filter,
    )
    if not base["configured"]:
        return TgStatus(**base, authorized=False,
                        message="TG_API_ID / TG_API_HASH backend/.env da yo'q")
    try:
        client = await tg.get_client()
        me = await client.get_me()
        return TgStatus(**base, authorized=True,
                        account=" ".join(
                            x for x in [me.first_name, me.last_name,
                                        f"(@{me.username})" if me.username else None] if x
                        ) or str(me.id),
                        message="Ulangan ✅")
    except tg.TelegramNotConfigured as exc:
        return TgStatus(**base, authorized=False, message=str(exc))


@router.get("/chats", response_model=list[TgChat])
async def tg_chats(current_user: CurrentUser) -> list[TgChat]:
    try:
        chats = await tg.list_chats()
    except tg.TelegramNotConfigured as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return [TgChat(id=c.id, title=c.title, username=c.username, kind=c.kind) for c in chats]
