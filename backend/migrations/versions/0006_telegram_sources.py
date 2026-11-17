"""Telegram: har kuzatiladigan chat — alohida manba (TG_CHATS va TG_LEAK_CHATS dan, bir marta)

- TG_CHATS ∪ TG_LEAK_CHATS dagi har chat → `Telegram: <kalit>` (kind telegram_user, config {"chat": kalit}).
  TG_LEAK_CHATS dagilar — qat'iy kategoriya `leak`.
- `translate`: ochiq kanal (username) — yoqiq; raqamli ID (yopiq chat) — o'chiq: yopiq guruh matni uchinchi
  tomonga (tarjima xizmati) faqat admin ruxsat bersa yuboriladi.
- TG_CHATS bo'sh bo'lsa — yagona "Telegram (akkaunt)" manbasi (barcha a'zo chatlar) qoladi.
- Eski "Telegram (akkaunt)" yozuvi o'chiriladi; uning hodisalari qoladi (source_id bo'shatiladi va per-chat manba
  o'sha xabarni qayta ko'rganda avtomatik bog'lanadi).

Revision ID: 0006_telegram_sources
Revises: 0005_event_uid_v2
Create Date: 2026-11-14
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_telegram_sources"
down_revision: str | None = "0005_event_uid_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY = "Telegram (akkaunt)"


def _chats() -> tuple[list[str], set[str]]:
    from app.core.config import settings

    chats = list(dict.fromkeys(settings.tg_chats_list + settings.tg_leak_chats_list))
    return chats, set(settings.tg_leak_chats_list)


def upgrade() -> None:
    chats, leak = _chats()
    if not chats:
        return
    conn = op.get_bind()
    leak_id = conn.execute(sa.text("select id from categories where slug = 'leak'")).scalar()
    for key in chats:
        conn.execute(sa.text(
            "insert into sources (name, kind, config, lang, category_id, scope, translate, interval_seconds, "
            "jitter_pct, backfill_days, notes) values (:name, 'telegram_user', cast(:config as jsonb), 'uz', :cat, "
            "'regional', :translate, 600, 20, 14, :notes) on conflict (name) do nothing"
        ), dict(
            name=f"Telegram: {key}"[:128], config=json.dumps({"chat": key}), cat=leak_id if key in leak else None,
            translate=not key.lstrip("-").isdigit(),
            notes="TG_LEAK_CHATS dan" if key in leak else "TG_CHATS dan",
        ))
    conn.execute(sa.text("delete from sources where name = :n and kind = 'telegram_user'"), {"n": LEGACY})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("delete from sources where kind = 'telegram_user' and config ? 'chat'"))
    conn.execute(sa.text(
        "insert into sources (name, kind, config, lang, interval_seconds) values (:n, 'telegram_user', '{}', 'uz', 300) "
        "on conflict (name) do nothing"
    ), {"n": LEGACY})
