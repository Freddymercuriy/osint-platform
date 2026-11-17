"""Xalqaro kiber-saytlar → Global: hudud filtri olinadi, scope `global`

Foydalanuvchi talabi: xalqaro kiber-saytlar (The Hacker News, SecurityWeek, Habr ...) Markaziy Osiyo tilga olinmasa ham
yig'ilsin — Events'ning "Global" bo'limida. Asosiy (regional) lenta o'zgarmaydi: global manbaning Markaziy Osiyo
haqidagi yangiligi baribir `regional` bo'ladi (pipeline).

- RSS: hudud filtri yoqiq, kiber filtri o'chiq manbalar (0004 dagi xalqaro kiber-saytlar to'plami).
- Google News `site:` so'rovlari (bloklangan saytlar): Markaziy Osiyo sharti so'rovdan olinadi.
- Hammasida `baseline_done = false` va ETag / Last-Modified tozalanadi: birinchi yig'ish backfill oynasidagi
  maqolalarni ogohlantirishsiz (baseline) yozadi — 🔔 oqimi bo'lmaydi.

Revision ID: 0014_international_cyber_global
Revises: 0013_source_wait_info
Create Date: 2026-11-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_international_cyber_global"
down_revision: str | None = "0013_source_wait_info"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CA = '(Uzbekistan OR Kazakhstan OR Kyrgyzstan OR Tajikistan OR Turkmenistan OR "Central Asia")'
SITES = {"BleepingComputer": "bleepingcomputer.com", "CyberNews": "cybernews.com",
         "The Cyber Express": "thecyberexpress.com"}
NOTE = " | Global (0014): hudud filtrisiz; Markaziy Osiyo haqidagisi baribir mintaqaviy."
_RESET = ("scope = 'global', region_filter = false, baseline_done = false, etag = null, last_modified = null, "
          "next_run_at = case when enabled then now() + random() * interval '10 minutes' else next_run_at end, "
          "notes = notes || :note")


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        f"update sources set {_RESET} where kind = 'rss' and region_filter and not cyber_filter"
    ), {"note": NOTE})
    for name, site in SITES.items():
        conn.execute(sa.text(
            f"update sources set {_RESET}, config = config || jsonb_build_object('query', cast(:q as text)) "
            "where name = :name and kind = 'google_news'"
        ), {"note": NOTE, "name": name, "q": f"site:{site} when:7d"})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        # faqat shu migratsiya belgilaganlar — keyin admin orqali qo'shilgan global RSS manbalariga tegilmaydi
        "update sources set scope = 'regional', region_filter = true, notes = replace(notes, :note, '') "
        "where kind = 'rss' and position(:note in notes) > 0"
    ), {"note": NOTE})
    for name, site in SITES.items():
        conn.execute(sa.text(
            "update sources set scope = 'regional', notes = replace(notes, :note, ''), "
            "config = config || jsonb_build_object('query', cast(:q as text)) "
            "where name = :name and kind = 'google_news'"
        ), {"note": NOTE, "name": name, "q": f"site:{site} {CA} when:7d"})
