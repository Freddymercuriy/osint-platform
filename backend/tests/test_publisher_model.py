"""Nashr ma'lumot modeli: standart qiymatlar, (manzil, dedup_key) noyobligi, cheklovlar, kaskad, holat qatori."""

from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import BotChat, ChannelDestination, ChannelPost, PublisherState, Reviewer
from app.services.publisher import outbox


async def _dest(db, **kw) -> ChannelDestination:
    d = ChannelDestination(name=kw.pop("name", "Rahbariyat"), **kw)
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def test_destination_defaults(db):
    d = await _dest(db)
    assert (d.mode, d.lang, d.is_test, d.enabled, d.paused) == ("dry_run", "uz", False, True, False)
    assert d.countries == ["UZ", "KZ", "KG", "TJ", "TM"] and d.categories == [] and not d.include_global
    assert (d.instant_min_band, d.brief_min_band, d.max_instant_per_day) == ("critical", "medium", 6)
    assert (d.daily_enabled, d.daily_time, d.daily_weekdays) == (True, time(8, 30), [1, 2, 3, 4, 5])
    assert (d.weekly_enabled, d.weekly_day, d.weekly_time) == (True, 1, time(8, 45))
    assert (d.quiet_enabled, d.quiet_start, d.quiet_end, d.quiet_policy) == (True, time(22, 0), time(7, 0), "uz_sound")
    assert (d.protect_content, d.show_original, d.explain_terms) == (False, True, True)
    assert d.enabled_at is not None and d.status == "unknown" and not d.is_public


@pytest.mark.parametrize("field,value", [("mode", "live"), ("lang", "de"), ("instant_min_band", "urgent"),
                                         ("quiet_policy", "loud"), ("weekly_day", 8)])
async def test_destination_constraints(db, field, value):
    db.add(ChannelDestination(name="X", **{field: value}))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_post_dedup_is_idempotent_and_constraints(db):
    d = await _dest(db)
    p1 = await outbox.insert_post(db, destination_id=d.id, kind="alert", dedup_key="alert:1", event_ids=[1],
                                  status="draft", text="<b>Salom</b>")
    assert p1 is not None and p1.status == "draft" and p1.final_text == "<b>Salom</b>"
    again = await outbox.insert_post(db, destination_id=d.id, kind="alert", dedup_key="alert:1", event_ids=[1])
    assert again is None  # ikkinchi tsikl / restart — takror yo'q
    await db.commit()
    assert len((await db.scalars(select(ChannelPost))).all()) == 1
    other = await _dest(db, name="Test kanal", is_test=True)
    assert await outbox.insert_post(db, destination_id=other.id, kind="alert", dedup_key="alert:1") is not None
    await db.commit()
    await db.refresh(p1)
    p1.edited_text = "<b>Tahrir</b>"
    await db.commit()
    await db.refresh(p1)
    assert p1.final_text == "<b>Tahrir</b>"
    did = d.id
    db.add(ChannelPost(destination_id=did, kind="alert", dedup_key="bad", status="published"))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
    db.add(ChannelPost(destination_id=did, kind="tweet", dedup_key="bad2"))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_reply_link_and_cascade(db):
    d = await _dest(db)
    parent = await outbox.insert_post(db, destination_id=d.id, kind="alert", dedup_key="alert:5", status="sent")
    child = await outbox.insert_post(db, destination_id=d.id, kind="update", dedup_key="update:5:critical",
                                     reply_to_post_id=parent.id)
    await db.commit()
    await db.delete(parent)
    await db.commit()
    await db.refresh(child)
    assert child.reply_to_post_id is None
    await db.delete(d)
    await db.commit()
    assert (await db.scalars(select(ChannelPost))).all() == []


async def test_state_row_bot_chats_and_reviewers(db):
    st = await outbox.get_state(db)
    assert st.id == 1 and st.paused is False and st.bot_status == "unknown" and st.updates_offset is None
    await db.delete(st)
    await db.commit()
    assert (await outbox.get_state(db)).id == 1  # yo'q bo'lsa — yaratiladi
    await db.commit()
    db.add(PublisherState(id=2))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
    db.add(BotChat(chat_id=-1001234567890, type="channel", title="Rahbariyat", status="administrator",
                   rights={"can_post_messages": True}))
    db.add(Reviewer(tg_user_id=111, name="Admin"))
    await db.commit()
    db.add(Reviewer(tg_user_id=111, name="Takror"))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
