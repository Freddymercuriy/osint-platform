"""DarkForums (.onion) manbasi — `onion_feed` ulagichi, Tor orqali, faqat kiber bo'limlarning mavzu sarlavhalari

Egasi qarori (2026-11-20): ".onion o'qilmaydi" qoidasiga istisno — faqat admin qo'shgan `onion_feed` manbalar, faqat
Tor orqali, faqat metadata (sarlavha, havola, vaqt, bo'lim, muallif taxallusi; post matni olinmaydi).

DarkForums — ma'lumotlar sizishi forumi (MyBB). Mehmon uchun ochiq `syndication.php` lentalari, kategoriya bo'yicha
5 so'rov: sizishlar (Databases, Premium Databases, Other Leaks, Premium Other Leaks, Source Codes), stealer loglar va
buzilgan akkauntlar, sotuv (Leaks Market, Access Market), Sellers Place (fraud), hacking (Malware, Exploit & POCs,
Software Vulnerabilities — kategoriya klassifikatordan). Olinmaydi: Doxes (xususiy shaxslar), Combolists, o'yinlar,
lounge va boshqa kiberga aloqasiz bo'limlar. Kuniga ~55–60 mavzu, scope `global` (Markaziy Osiyo tilga olinsa —
mintaqaviy lentaga), ishonchlilik `underground` (kanalga faqat tasdiq bilan).

Revision ID: 0024_onion_forum_source
Revises: 0023_event_images
Create Date: 2026-11-20
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_onion_forum_source"
down_revision: str | None = "0023_event_images"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "DarkForums (Tor)"
BASE = "http://darkfoxaqhfpxkrbt7vxns2z2u2k72sgmqbzeorupaiottw3ecm2wgyd.onion/syndication.php"
FEEDS = [
    ("10,47,13,51,12", "leak", "Databases / Other Leaks / Source Codes"),
    ("52,15", "credentials", "Stealer Logs / Cracked Accounts"),
    ("81,82", "darkweb-sale", "Leaks Market / Access Market"),
    ("21", "fraud", "Sellers Place"),
    ("67,70,66", None, "Hacking: Malware / Exploits"),
]
CONFIG = {
    "site": "DarkForums",
    "feeds": [{"url": f"{BASE}?fid={fids}&limit=50", "category": cat, "section": sec} for fids, cat, sec in FEEDS],
    "repost_memory": 500,
}
NOTES = ("Tor orqali (TOR_PROXY_URL, docker-compose `tor` xizmati). Faqat mavzu sarlavhalari — post matni, fayllar, "
         "mavzu sahifalari olinmaydi. Doxes / Combolists va kiberga aloqasiz bo'limlar ataylab yo'q. Bo'limlar: MyBB "
         "fid raqamlari (misc.php?action=syndication). Login / CAPTCHA chiqsa — chetlab o'tilmaydi (blocked).")


def upgrade() -> None:
    op.get_bind().execute(sa.text(
        "insert into sources (name, kind, config, lang, scope, region_filter, cyber_filter, translate, "
        "interval_seconds, jitter_pct, backfill_days, enabled, status, reliability, notes) values (:name, "
        "'onion_feed', cast(:config as jsonb), 'en', 'global', false, false, true, 1800, 20, 3, true, 'never_run', "
        "'underground', :notes) on conflict (name) do nothing"
    ), {"name": NAME, "config": json.dumps(CONFIG), "notes": NOTES})


def downgrade() -> None:
    # Hodisalar qoladi (events.source_id → NULL), manba yozuvi va uning tarixi (source_runs) o'chadi
    op.get_bind().execute(sa.text("delete from sources where name = :name and kind = 'onion_feed'"), {"name": NAME})
