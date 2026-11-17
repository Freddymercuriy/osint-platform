"""Outbox yordamchilari: postni bir martalik (idempotent) qo'shish va publisher holati qatori.

`(destination_id, dedup_key)` noyob: restart, ikki marta ishlagan tsikl yoki ikki jarayon bir postni ikki marta
yarata olmaydi — `INSERT ... ON CONFLICT DO NOTHING`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChannelPost, PublisherState


async def insert_post(db: AsyncSession, *, destination_id: int, kind: str, dedup_key: str,
                      **fields: Any) -> ChannelPost | None:
    """Yangi post (qaytaradi) yoki shu kalit bilan post allaqachon bor bo'lsa — None. Commit qilinmaydi."""
    stmt = (insert(ChannelPost)
            .values(destination_id=destination_id, kind=kind, dedup_key=dedup_key[:160], **fields)
            .on_conflict_do_nothing(constraint="uq_channel_posts_destination_dedup")
            .returning(ChannelPost.id))
    new_id = (await db.execute(stmt)).scalar_one_or_none()
    if new_id is None:
        return None
    return await db.get(ChannelPost, new_id)


async def get_state(db: AsyncSession) -> PublisherState:
    """`publisher_state` qatori (migratsiya yaratadi; yo'q bo'lsa — yaratiladi)."""
    st = await db.get(PublisherState, 1)
    if st is None:
        await db.execute(insert(PublisherState).values(id=1).on_conflict_do_nothing())
        await db.flush()
        st = await db.get(PublisherState, 1)
    assert st is not None
    return st


async def find_post(db: AsyncSession, destination_id: int, dedup_key: str) -> ChannelPost | None:
    return await db.scalar(select(ChannelPost).where(ChannelPost.destination_id == destination_id,
                                                     ChannelPost.dedup_key == dedup_key))
