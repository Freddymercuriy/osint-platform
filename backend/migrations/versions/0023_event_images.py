"""Hodisa rasmlari (`event_images`) va post turi `followup` (rasmli postning davomi)

Har hodisaning 16:9 rasmi: maqolaning o'z rasmi (`source`, og:image / RSS media) yoki platforma chizgan
illyustratsiya (`generated`), ular ham bo'lmasa — rubrika zaxira rasmi (`fallback`). Fayllar diskda (`MEDIA_DIR`),
jadvalda — meta: tur, asl URL, versiya (kesh), manba rasmi tekshirilganmi, xato sababi.

Kanal postlari endi rasm + izoh (caption, 1024 belgi); izohga sig'magan bo'limlar (asosiy ma'lumotlar, tavsiya)
`followup` postida — rasmli postga javob (reply) sifatida.

Revision ID: 0023_event_images
Revises: 0022_require_translation
Create Date: 2026-11-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_event_images"
down_revision: str | None = "0022_require_translation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS_OLD = ("alert", "group", "daily", "weekly", "update", "correction", "test")
KINDS_NEW = KINDS_OLD + ("followup",)
CK_KIND = "ck_channel_posts_kind"


def _in(col: str, values: Sequence[str]) -> str:
    return f"{col} in ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "event_images",
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("version", sa.String(16), nullable=False),
        sa.Column("rubric", sa.String(16), nullable=True),
        sa.Column("motif", sa.String(24), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_hash", sa.String(16), nullable=True),
        sa.Column("source_checked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(_in("kind", ("source", "generated", "fallback")), name="ck_event_images_kind"),
    )
    op.create_index("ix_event_images_source_hash", "event_images", ["source_hash"])
    op.create_index("ix_event_images_unchecked", "event_images", ["source_checked"],
                    postgresql_where=sa.text("source_checked = false"))
    op.drop_constraint(CK_KIND, "channel_posts", type_="check")
    op.create_check_constraint(CK_KIND, "channel_posts", _in("kind", KINDS_NEW))


def downgrade() -> None:
    op.execute("delete from channel_posts where kind = 'followup'")
    op.drop_constraint(CK_KIND, "channel_posts", type_="check")
    op.create_check_constraint(CK_KIND, "channel_posts", _in("kind", KINDS_OLD))
    op.drop_index("ix_event_images_unchecked", table_name="event_images")
    op.drop_index("ix_event_images_source_hash", table_name="event_images")
    op.drop_table("event_images")
