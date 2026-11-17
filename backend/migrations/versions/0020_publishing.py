"""Nashr ma'lumot modeli (rahbariyat kanali, Bosqich 2): kanallar, postlar (outbox + audit), bot chatlari,
tasdiqlovchilar, publisher holati

- `channel_destinations` — bot post qiladigan har bir Telegram chat: til, rejim (dry_run → review → auto; har yangi
  kanal dry_run da), test belgisi, qamrov (davlatlar, global, kategoriyalar), bandlar, jadval (kunlik / haftalik),
  sokin soatlar, kunlik chegara, variantlar, holat va sog'liq.
- `channel_posts` — rahbariyatga nima aytilganining izi: tur, hodisalar, (manzil, dedup_key) noyob, holat, muzlatilgan
  matn, tahrir, tugmalar, rasm (haftalik grafik), javob qilingan post, yetkazish (message_id, urinishlar, xato — token
  yashirilgan), kim tasdiqlagani, yuborish paytidagi band va manbalar soni. Kamida 1 yil saqlanadi.
- `bot_chats` — bot qo'shilgan / unga yozgan chatlar (`my_chat_member`, `/start`) — admin chat ID'ni qo'lda
  ko'chirmasdan tanlaydi.
- `reviewers` — tasdiqlashga ruxsat etilgan Telegram foydalanuvchilari.
- `publisher_state` — bitta qator: `getUpdates` offset, umumiy pauza, tekshiruv chati, bot holati.

Revision ID: 0020_publishing
Revises: 0019_qilin_word_watch_agencies
Create Date: 2026-11-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_publishing"
down_revision: str | None = "0019_qilin_word_watch_agencies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POST_KINDS = ("alert", "group", "daily", "weekly", "update", "correction", "test")
POST_STATUSES = ("waiting_translation", "draft", "awaiting_approval", "queued", "sending", "sent", "failed",
                 "skipped", "rejected", "expired", "unknown")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} in (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "channel_destinations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("chat_title", sa.String(255), nullable=True),
        sa.Column("chat_type", sa.String(16), nullable=True),
        sa.Column("chat_username", sa.String(64), nullable=True),
        sa.Column("topic_id", sa.Integer(), nullable=True),
        sa.Column("lang", sa.String(8), server_default="uz", nullable=False),
        sa.Column("mode", sa.String(8), server_default="dry_run", nullable=False),
        sa.Column("is_test", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("countries", postgresql.ARRAY(sa.String(2)), server_default=sa.text("'{UZ,KZ,KG,TJ,TM}'"),
                  nullable=False),
        sa.Column("include_global", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("categories", postgresql.ARRAY(sa.String(48)), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("instant_min_band", sa.String(8), server_default="critical", nullable=False),
        sa.Column("brief_min_band", sa.String(8), server_default="medium", nullable=False),
        sa.Column("daily_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("daily_time", sa.Time(), server_default=sa.text("'08:30'"), nullable=False),
        sa.Column("daily_weekdays", postgresql.ARRAY(sa.SmallInteger()), server_default=sa.text("'{1,2,3,4,5}'"),
                  nullable=False),
        sa.Column("weekly_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("weekly_day", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("weekly_time", sa.Time(), server_default=sa.text("'08:45'"), nullable=False),
        sa.Column("quiet_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("quiet_start", sa.Time(), server_default=sa.text("'22:00'"), nullable=False),
        sa.Column("quiet_end", sa.Time(), server_default=sa.text("'07:00'"), nullable=False),
        sa.Column("quiet_policy", sa.String(16), server_default="uz_sound", nullable=False),
        sa.Column("max_instant_per_day", sa.SmallInteger(), server_default="6", nullable=False),
        sa.Column("protect_content", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("show_original", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("explain_terms", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("enabled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("paused", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("paused_reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(12), server_default="unknown", nullable=False),
        sa.Column("down_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rights", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("rights_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("lang in ('uz', 'uz-Cyrl', 'ru', 'en')", name="ck_channel_destinations_lang"),
        sa.CheckConstraint("mode in ('dry_run', 'review', 'auto')", name="ck_channel_destinations_mode"),
        sa.CheckConstraint("instant_min_band in ('low', 'medium', 'high', 'critical') and "
                           "brief_min_band in ('low', 'medium', 'high', 'critical')",
                           name="ck_channel_destinations_bands"),
        sa.CheckConstraint("quiet_policy in ('uz_sound', 'all_silent', 'hold')",
                           name="ck_channel_destinations_quiet_policy"),
        sa.CheckConstraint("status in ('unknown', 'ok', 'down')", name="ck_channel_destinations_status"),
        sa.CheckConstraint("weekly_day between 1 and 7", name="ck_channel_destinations_weekly_day"),
        sa.CheckConstraint("max_instant_per_day between 0 and 100", name="ck_channel_destinations_max_instant"),
    )

    op.create_table(
        "channel_posts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("destination_id", sa.Integer(), sa.ForeignKey("channel_destinations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("event_ids", postgresql.ARRAY(sa.Integer()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("dedup_key", sa.String(160), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("lang", sa.String(8), nullable=True),
        sa.Column("text", sa.Text(), server_default="", nullable=False),
        sa.Column("edited_text", sa.Text(), nullable=True),
        sa.Column("buttons", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("photo", sa.LargeBinary(), nullable=True),
        sa.Column("silent", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("reply_to_post_id", sa.BigInteger(), sa.ForeignKey("channel_posts.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("priority", sa.SmallInteger(), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("skip_reason", sa.String(64), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by_tg_id", sa.BigInteger(), nullable=True),
        sa.Column("approved_by_name", sa.String(128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("review_message_id", sa.BigInteger(), nullable=True),
        sa.Column("band_at_send", sa.String(8), nullable=True),
        sa.Column("sources_at_send", sa.SmallInteger(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(_in("kind", POST_KINDS), name="ck_channel_posts_kind"),
        sa.CheckConstraint(_in("status", POST_STATUSES), name="ck_channel_posts_status"),
        sa.UniqueConstraint("destination_id", "dedup_key", name="uq_channel_posts_destination_dedup"),
    )
    op.create_index("ix_channel_posts_status_next", "channel_posts", ["status", "next_attempt_at"])
    op.create_index("ix_channel_posts_destination_created", "channel_posts", ["destination_id", "created_at"])
    op.create_index("ix_channel_posts_event_ids", "channel_posts", ["event_ids"], postgresql_using="gin")

    op.create_table(
        "bot_chats",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rights", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("added_by_tg_id", sa.BigInteger(), nullable=True),
        sa.Column("added_by_name", sa.String(128), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "reviewers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "publisher_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("updates_offset", sa.BigInteger(), nullable=True),
        sa.Column("paused", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("paused_reason", sa.Text(), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("bot_id", sa.BigInteger(), nullable=True),
        sa.Column("bot_username", sa.String(64), nullable=True),
        sa.Column("bot_status", sa.String(16), server_default="unknown", nullable=False),
        sa.Column("bot_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_publisher_state_single"),
        sa.CheckConstraint("bot_status in ('unknown', 'missing', 'ok', 'invalid', 'conflict', 'error')",
                           name="ck_publisher_state_bot_status"),
    )
    op.execute("insert into publisher_state (id) values (1)")


def downgrade() -> None:
    op.drop_table("publisher_state")
    op.drop_table("reviewers")
    op.drop_table("bot_chats")
    op.drop_index("ix_channel_posts_event_ids", table_name="channel_posts")
    op.drop_index("ix_channel_posts_destination_created", table_name="channel_posts")
    op.drop_index("ix_channel_posts_status_next", table_name="channel_posts")
    op.drop_table("channel_posts")
    op.drop_table("channel_destinations")
