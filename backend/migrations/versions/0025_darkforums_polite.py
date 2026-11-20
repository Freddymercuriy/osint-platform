"""DarkForums: bloklanmaslik qoidalari — kam so'rov, bo'lim jadvali, kunlik limit; Premium bo'limlar olib tashlandi

- Premium Databases (47) va Premium Other Leaks (51) mehmonga bo'sh (0 mavzu; login + pullik akkaunt kerak) —
  so'rovdan olib tashlandi.
- Manba intervali 30 → 60 daqiqa. Lentalar o'z hajmiga mos: sizishlar (~30 / kun) har yig'ishda, stealer / sotuv —
  2 soatda, Sellers Place — 3 soatda, hacking (~0,1 / kun) — 12 soatda. Sahifa 50 → 10–30 mavzu.
  So'rovlar: kuniga ~240 → ~58; qat'iy limit — 80 / kun (`max_requests_per_day`).

Admin config'ni o'zgartirgan bo'lsa (0024 dagidan farq qilsa) — tegilmaydi.

Revision ID: 0025_darkforums_polite
Revises: 0024_onion_forum_source
Create Date: 2026-11-20
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_darkforums_polite"
down_revision: str | None = "0024_onion_forum_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "DarkForums (Tor)"
BASE = "http://darkfoxaqhfpxkrbt7vxns2z2u2k72sgmqbzeorupaiottw3ecm2wgyd.onion/syndication.php"

OLD_FEEDS = [
    ("10,47,13,51,12", "leak", "Databases / Other Leaks / Source Codes"),
    ("52,15", "credentials", "Stealer Logs / Cracked Accounts"),
    ("81,82", "darkweb-sale", "Leaks Market / Access Market"),
    ("21", "fraud", "Sellers Place"),
    ("67,70,66", None, "Hacking: Malware / Exploits"),
]
OLD = {
    "site": "DarkForums",
    "feeds": [{"url": f"{BASE}?fid={fids}&limit=50", "category": cat, "section": sec} for fids, cat, sec in OLD_FEEDS],
    "repost_memory": 500,
}

# (fid'lar, kategoriya, bo'lim, sahifa, har necha daqiqada)
NEW_FEEDS = [
    ("10,13,12", "leak", "Databases / Other Leaks / Source Codes", 30, 0),
    ("52,15", "credentials", "Stealer Logs / Cracked Accounts", 20, 120),
    ("81,82", "darkweb-sale", "Leaks Market / Access Market", 20, 120),
    ("21", "fraud", "Sellers Place", 20, 180),
    ("67,70,66", None, "Hacking: Malware / Exploits", 10, 720),
]
NEW = {
    "site": "DarkForums",
    "feeds": [{"url": f"{BASE}?fid={fids}&limit={limit}", "category": cat, "section": sec, "every_minutes": every}
              for fids, cat, sec, limit, every in NEW_FEEDS],
    "repost_memory": 500,
    "max_requests_per_day": 80,
}


def _swap(src: dict, dst: dict, interval_from: int, interval_to: int) -> None:
    op.get_bind().execute(sa.text(
        "update sources set config = cast(:dst as jsonb), "
        "interval_seconds = case when interval_seconds = :ifrom then :ito else interval_seconds end, "
        "updated_at = now() where name = :name and kind = 'onion_feed' and config = cast(:src as jsonb)"
    ), {"name": NAME, "src": json.dumps(src), "dst": json.dumps(dst), "ifrom": interval_from, "ito": interval_to})


def upgrade() -> None:
    _swap(OLD, NEW, 1800, 3600)


def downgrade() -> None:
    _swap(NEW, OLD, 3600, 1800)
