"""Telegram manbalari → Global + kiber filtri (Markaziy Osiyo haqidagisi baribir asosiy lentaga)

Tahlil (2026-11-17): 43 ta Telegram manbasining so'nggi 2728 xabaridan faqat 31 tasi (~1%) Markaziy Osiyo kalit
so'zlari filtridan o'tardi; 460 tasi kiberxavfsizlik haqida, lekin mintaqa tilga olinmagani uchun tashlanardi.
Foydalanuvchi tanlovi: barcha kanallar Global (kiber filtri bilan). Mintaqa kalit so'zi (`TG_UZ_FILTER`,
`TG_EXTRA_KEYWORDS`) topilgan xabar avvalgidek `regional` — asosiy lenta kamaymaydi (ulagich + `apply_filters`).

- Kursor (`state.last_id`) olib tashlanadi: birinchi yig'ish har chatning so'nggi `TG_MESSAGES_PER_CHAT` xabarini
  qayta o'qiydi; `baseline_done = false` — bu yozuvlar ogohlantirishsiz (🔔 oqimi yo'q).
- Downgrade: scope / filtr qaytariladi (kursor qaytarilmaydi — keyingi yig'ish oxirgi xabarlarni qayta o'qiydi).

Revision ID: 0016_telegram_global
Revises: 0015_cap_future_published
Create Date: 2026-11-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_telegram_global"
down_revision: str | None = "0015_cap_future_published"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTE = " | Global (0016): kiber filtri; Markaziy Osiyo kalit so'zi bo'lsa — mintaqaviy."


def upgrade() -> None:
    op.get_bind().execute(sa.text(
        "update sources set scope = 'global', cyber_filter = true, region_filter = false, baseline_done = false, "
        "state = coalesce(state, '{}'::jsonb) - 'last_id', "
        "next_run_at = case when enabled then now() + random() * interval '10 minutes' else next_run_at end, "
        "notes = coalesce(notes, '') || :note "
        "where kind = 'telegram_user'"
    ), {"note": NOTE})


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "update sources set scope = 'regional', cyber_filter = false, notes = replace(notes, :note, '') "
        "where kind = 'telegram_user' and position(:note in notes) > 0"
    ), {"note": NOTE})
