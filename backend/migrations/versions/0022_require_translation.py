"""Kanal: `require_translation` (post faqat kanal tilida) va kunlik chegara 1000 gacha (yangiliklar lentasi)

Yangiliklar lentasi kanali uchun ("har bir yangilik o'zbekcha"): tarjima `PUBLISHER_TRANSLATION_WAIT_MINUTES` ichida
tayyor bo'lmasa ham asl tildagi matn izoh bilan yuborilmaydi — post tarjima tayyor bo'lguncha (hodisa 6 soatdan
eskirmaguncha) kutadi, keyin `skipped` (`translation_missing`). Standart — false (rahbariyat kanali spetsifikatsiyasi).
`max_instant_per_day` chegarasi 100 → 1000: lenta kanaliga kuniga ~220 hodisa (rahbariyat kanali standarti — 6).

Revision ID: 0022_require_translation
Revises: 0021_category_texts
Create Date: 2026-11-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_require_translation"
down_revision: str | None = "0021_category_texts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CK = "ck_channel_destinations_max_instant"


def upgrade() -> None:
    op.add_column("channel_destinations",
                  sa.Column("require_translation", sa.Boolean(), server_default="false", nullable=False))
    op.drop_constraint(CK, "channel_destinations", type_="check")
    op.create_check_constraint(CK, "channel_destinations", "max_instant_per_day between 0 and 1000")


def downgrade() -> None:
    op.execute("update channel_destinations set max_instant_per_day = 100 where max_instant_per_day > 100")
    op.drop_constraint(CK, "channel_destinations", type_="check")
    op.create_check_constraint(CK, "channel_destinations", "max_instant_per_day between 0 and 100")
    op.drop_column("channel_destinations", "require_translation")
