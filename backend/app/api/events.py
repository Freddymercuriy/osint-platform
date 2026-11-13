from fastapi import APIRouter, Query

from app.api.deps import CurrentUser
from app.schemas import EventItemOut, EventsResponse
from app.services.events.aggregator import fetch_events

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=EventsResponse)
async def list_events(
    current_user: CurrentUser,
    limit: int = Query(40, ge=1, le=100),
    q: str | None = Query(None, description="Sarlavha/matn bo'yicha filtr"),
) -> EventsResponse:
    items = await fetch_events(limit=limit, query=q)
    return EventsResponse(
        count=len(items),
        items=[EventItemOut.model_validate(i) for i in items],
    )
