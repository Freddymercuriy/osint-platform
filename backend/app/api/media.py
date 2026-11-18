"""Hodisa rasmlari: `GET /api/media/events/{id}.jpg?size=s|l&v=<versiya>&sig=<imzo>`.

`<img>` so'rovida Authorization sarlavhasi yo'q — havola HMAC bilan imzolangan (`media.store.sign`), imzosi to'g'ri
kelmasa 404 (rasm borligi ham bildirilmaydi). Fayl tayyor bo'lsa — bazaga murojaatsiz beriladi; hali tayyorlanmagan
bo'lsa — shu yerning o'zida mahalliy illyustratsiya chiziladi (tarmoqqa chiqilmaydi; bir vaqtda ko'pi bilan
`DRAW_CONCURRENCY` ta — sahifa 60 ta kartani birdan so'rasa ham baza ulanishlari va CPU band bo'lib qolmasin).
Fon ishchisi keyinroq maqolaning o'z rasmini topsa almashtiradi — API yangi versiyali havola beradi.
URL'da versiya bo'lsa (`v` ≠ 0) — uzoq kesh (havola rasm bilan birga o'zgaradi), aks holda qisqa.
"""

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response

from app.api.deps import DbSession
from app.models import EventRecord
from app.services.media import service, store

router = APIRouter(prefix="/api/media", tags=["media"])
DRAW_CONCURRENCY = 4
_draw_gate = asyncio.Semaphore(DRAW_CONCURRENCY)


@router.get("/events/{event_id}.jpg", responses={200: {"content": {"image/jpeg": {}}}})
async def event_image(
    event_id: int,
    db: DbSession,
    sig: str = Query("", max_length=64),
    size: Literal["s", "l"] = "s",
    v: str | None = Query(None, max_length=16),
) -> Response:
    if not store.verify(event_id, sig):
        raise HTTPException(status_code=404)
    data = await asyncio.to_thread(store.read, event_id, size)
    if data is None:
        async with _draw_gate:
            ev = await db.get(EventRecord, event_id)
            if ev is None:
                raise HTTPException(status_code=404)
            await service.ensure_image(db, ev, fetch=False)
            await db.commit()
        data = await asyncio.to_thread(store.read, event_id, size)
        if data is None:
            raise HTTPException(status_code=404)
    versioned = bool(v) and v != "0"
    return Response(content=data, media_type="image/jpeg", headers={
        "Cache-Control": "private, max-age=31536000, immutable" if versioned else "private, max-age=300",
        "ETag": f'"{store.version_of(data)}"',
        "X-Content-Type-Options": "nosniff",
    })
