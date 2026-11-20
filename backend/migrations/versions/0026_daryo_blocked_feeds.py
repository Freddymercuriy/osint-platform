"""Daryo.uz: RSS yopildi (HTTP 403) — UZ rasmiy Telegram kanaliga, RU Google News'ga o'tkazildi

2026-11-19 dan daryo.uz yangi dvigatelga (Next.js) o'tdi va avtomatik so'rovlarni Cloudflare qoidasi bilan yopdi:
`/feed/`, `/ru/feed/`, saytning o'zi e'lon qilgan `/oz/rss-full/`, `sitemap.xml`, `news-sitemap.xml` va keshlanmagan
sahifalar — 403 "Request forbidden by administrative rules". Brauzerga o'xshab niqoblanish qoidaga zid, shuning uchun:
- Daryo.uz (UZ) → `telegram` (t.me/s/Daryo — sayt sahifasida ko'rsatilgan rasmiy kanal, 568K obunachi);
- Daryo.uz (RU) → `google_news` (`site:daryo.uz`, rus nashri; Google News'da o'zbekcha nashr yo'q).
Ikkalasida ham saytning o'ziga murojaat qilinmaydi. Havolalar boshqa (t.me / news.google.com) bo'lgani uchun birinchi
yig'ish — baseline (ogohlantirishsiz). Admin config'ni o'zgartirgan bo'lsa — tegilmaydi.

Revision ID: 0026_daryo_blocked_feeds
Revises: 0025_darkforums_polite
Create Date: 2026-11-20
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_daryo_blocked_feeds"
down_revision: str | None = "0025_darkforums_polite"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTE_UZ = ("daryo.uz RSS 2026-11-19 dan 403 (Cloudflare) — rasmiy Telegram kanali (t.me/Daryo) orqali o'qiladi; "
           "saytning o'ziga so'rov yuborilmaydi.")
NOTE_RU = ("daryo.uz RSS 2026-11-19 dan 403 (Cloudflare) — Google News (site:daryo.uz, rus nashri) orqali; "
           "saytning o'ziga so'rov yuborilmaydi.")

# (nomi, eski tur, eski config, eski interval, yangi tur, yangi config, yangi interval, izoh)
SWAPS = [
    ("Daryo.uz (UZ)", "rss", {"url": "https://daryo.uz/feed/"}, 600,
     "telegram", {"channel": "Daryo"}, 600, NOTE_UZ),
    ("Daryo.uz (RU)", "rss", {"url": "https://daryo.uz/ru/feed/"}, 600,
     "google_news", {"query": "site:daryo.uz when:7d"}, 1800, NOTE_RU),
]


def _swap(name: str, kind_from: str, cfg_from: dict, kind_to: str, cfg_to: dict,
          interval_from: int, interval_to: int, notes: str) -> None:
    op.get_bind().execute(sa.text(
        "update sources set kind = :kto, config = cast(:cto as jsonb), notes = :notes, "
        "interval_seconds = case when interval_seconds = :ifrom then :ito else interval_seconds end, "
        "baseline_done = false, state = '{}'::jsonb, etag = null, last_modified = null, "
        "status = case when enabled then 'never_run' else status end, last_error = null, last_http_status = null, "
        "consecutive_failures = 0, down_since = null, retry_after_seconds = null, last_outcome = null, "
        "next_run_at = null, updated_at = now() "  # scheduler bir interval ichida tarqatib rejalashtiradi
        "where name = :name and kind = :kfrom and config = cast(:cfrom as jsonb)"
    ), {"name": name, "kfrom": kind_from, "cfrom": json.dumps(cfg_from), "kto": kind_to, "cto": json.dumps(cfg_to),
        "ifrom": interval_from, "ito": interval_to, "notes": notes})


def upgrade() -> None:
    for name, k_old, c_old, i_old, k_new, c_new, i_new, note in SWAPS:
        _swap(name, k_old, c_old, k_new, c_new, i_old, i_new, note)


def downgrade() -> None:
    for name, k_old, c_old, i_old, k_new, c_new, i_new, _note in SWAPS:
        _swap(name, k_new, c_new, k_old, c_old, i_new, i_old, "")
