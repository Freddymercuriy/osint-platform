"""Ustuvorlik (rahbariyat kanali, Bosqich 1): hodisa balli / band / sabablar, manba ishonchliligi, kuzatuv ro'yxati,
publisher sozlamalari (og'irliklar va band chegaralari)

- `events.priority` (0–100), `priority_band` (low | medium | high | critical), `priority_reasons` ([{code, points, arg?}]).
  Qiymatlar ilova ishga tushganda hisoblanadi (housekeeping: `priority is null` hodisalar) — migratsiya hisoblamaydi.
- `sources.reliability`: official | tracker | media | community | underground — ulagich turi va nomidan:
  official — milliy CERT'lar (UZCERT, KZ-CERT, CERT.TJ, KG-CERT, sts.kz), CISA KEV, NVD; tracker — ransomware.live,
  RansomLook, HIBP, abuse.ch, OpenPhish, OTX, Cloudflare Radar; media — RSS, Google News, NewsNow; community —
  Telegram; underground — `TG_LEAK_CHATS` dagi va qat'iy kategoriyasi leak / darkweb-sale bo'lgan Telegram chatlari.
- `watchlist` — `TG_EXTRA_KEYWORDS` dan tashkilot / brendlar (joy nomlari — toshkent, namangan ... — olinmaydi).
  Umumiy so'zlar ("soliq" = soliq, "mehnat" = mehnat, "ipoteka" = ipoteka) yolg'iz alias qilinmaydi — aniq nom bilan.
- `publisher_settings` — bitta qator (id = 1): og'irliklar va band chegaralari (admin tahrirlaydi).

Revision ID: 0018_priority
Revises: 0017_leak_rules
Create Date: 2026-11-17
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_priority"
down_revision: str | None = "0017_leak_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RELIABILITY = ("official", "tracker", "media", "community", "underground")
TRACKER_KINDS = ("ransomware_live", "ransomware_live_pro", "ransomlook", "hibp_breaches", "threatfox", "urlhaus",
                 "openphish", "otx_pulses", "cloudflare_radar")
OFFICIAL_KINDS = ("cisa_kev", "nvd_cves")
OFFICIAL_NAME_RE = r"(cert\M|sts\.kz|kcokb)"  # UZCERT, KZ-CERT, CERT.TJ, KG-CERT; "certificate" emas
WATCH_KINDS = ("organisation", "domain", "brand", "product", "person")

# Muzlatilgan boshlang'ich qiymatlar (kodda — `services/publisher/priority.py::DEFAULT_*`, bir xil)
WEIGHTS = {
    "severity": {"critical": 50, "high": 35, "medium": 20, "low": 10, "info": 0},
    "country_uz": 30, "country_ca": 15,
    "sector": 10, "sectors": ["government", "finance", "telecom", "energy", "healthcare"],
    "watch_org": 40, "watch_product": 25, "watch_person": 30,
    "official": 10, "extra_source": 5, "extra_source_max": 2,
    "records_100k": 5, "records_1m": 10,
    "stale": -20, "stale_hours": 48,
    "underground_only": -10,
}
BANDS = {"critical": 80, "high": 60, "medium": 40}

# TG_EXTRA_KEYWORDS → kuzatuv ro'yxati. Kalit — .env dagi so'z; (tur, nom, aliaslar, izoh)
KNOWN = {
    "uzcard": ("brand", "Uzcard", ["uzcard", "Узкард"], ""),
    "humo": ("brand", "Humo", ["humo", "Хумо"], ""),
    "payme": ("brand", "Payme", ["payme", "Пейми"], ""),
    "ucell": ("organisation", "Ucell", ["ucell", "Юселл"], ""),
    "uztelecom": ("organisation", "Uztelecom", ["uztelecom", "Узтелеком", "O'zbektelekom"], ""),
    "uzmobile": ("brand", "Uzmobile", ["uzmobile", "Узмобайл"], ""),
    "mobiuz": ("brand", "Mobiuz", ["mobiuz", "Мобиуз"], ""),
    "beeline uz": ("organisation", "Beeline Uzbekistan", ["beeline uz", "Beeline Uzbekistan", "Билайн Узбекистан"], ""),
    "kapitalbank": ("organisation", "Kapitalbank", ["kapitalbank", "Капиталбанк"], ""),
    "agrobank": ("organisation", "Agrobank", ["agrobank", "Агробанк"], ""),
    "xalq banki": ("organisation", "Xalq banki", ["xalq banki", "Халк банк", "Народный банк Узбекистана"], ""),
    "ipoteka": ("organisation", "Ipoteka-bank", ["ipoteka bank", "ipoteka-bank", "ipotekabank", "Ипотека-банк",
                                                  "Ипотека банк"],
                "TG_EXTRA_KEYWORDS: 'ipoteka' umumiy so'z (ipoteka krediti) — faqat bank nomi bilan."),
    "hamkorbank": ("organisation", "Hamkorbank", ["hamkorbank", "Хамкорбанк"], ""),
    "uzum": ("brand", "Uzum", ["uzum", "Узум"], ""),
    "soliq": ("organisation", "Davlat soliq qo'mitasi", ["soliq.uz", "soliq qo'mitasi", "Davlat soliq qo'mitasi",
                                                        "Налоговый комитет Узбекистана"],
              "TG_EXTRA_KEYWORDS: 'soliq' umumiy so'z — faqat qo'mita nomi va soliq.uz bilan."),
    "my.gov": ("domain", "my.gov.uz", ["my.gov.uz", "my.gov"], ""),
    "egov": ("organisation", "Elektron hukumat (e-gov)", ["egov", "e-gov", "e-gov.uz", "Электронное правительство"], ""),
    "mehnat": ("organisation", "Bandlik va mehnat vazirligi", ["mehnat.uz", "Bandlik va mehnat vazirligi",
                                                              "Министерство занятости"],
               "TG_EXTRA_KEYWORDS: 'mehnat' umumiy so'z — faqat vazirlik nomi va mehnat.uz bilan."),
    "iiv": ("organisation", "Ichki ishlar vazirligi (IIV)", ["IIV", "Ichki ishlar vazirligi", "МВД Узбекистана"], ""),
    "dxx": ("organisation", "Davlat xavfsizlik xizmati (DXX)", ["DXX", "Davlat xavfsizlik xizmati",
                                                               "СГБ Узбекистана"], ""),
}


def _keywords() -> list[str]:
    try:
        from app.core.config import settings

        return settings.tg_extra_keywords_list
    except Exception:  # noqa: BLE001 — sozlama o'qilmasa ham migratsiya o'tsin
        return []


def _is_place(word: str) -> bool:
    from app.services.events.filters import region_hits

    return bool(region_hits(word))


def _leak_chats() -> list[str]:
    try:
        from app.core.config import settings

        return settings.tg_leak_chats_list
    except Exception:  # noqa: BLE001
        return []


def upgrade() -> None:
    op.add_column("events", sa.Column("priority", sa.SmallInteger(), nullable=True))
    op.add_column("events", sa.Column("priority_band", sa.String(8), nullable=True))
    op.add_column("events", sa.Column("priority_reasons", postgresql.JSONB(), server_default="[]", nullable=False))
    op.create_index("ix_events_priority", "events", ["priority"])
    op.create_index("ix_events_priority_band", "events", ["priority_band"])
    op.create_check_constraint("ck_events_priority_band", "events",
                               "priority_band is null or priority_band in ('low', 'medium', 'high', 'critical')")

    op.add_column("sources", sa.Column("reliability", sa.String(12), server_default="media", nullable=False))
    op.create_check_constraint("ck_sources_reliability", "sources",
                               "reliability in ('official', 'tracker', 'media', 'community', 'underground')")
    conn = op.get_bind()
    conn.execute(sa.text("update sources set reliability = 'tracker' where kind = any(:k)"), {"k": list(TRACKER_KINDS)})
    conn.execute(sa.text(
        "update sources set reliability = 'official' where kind = any(:k) "
        "or (kind in ('rss', 'html_list') and name ~* :re)"
    ), {"k": list(OFFICIAL_KINDS), "re": OFFICIAL_NAME_RE})
    conn.execute(sa.text("update sources set reliability = 'community' where kind = 'telegram_user'"))
    conn.execute(sa.text(
        "update sources s set reliability = 'underground' where s.kind = 'telegram_user' and ("
        "  lower(ltrim(s.config->>'chat', '@')) = any(:chats) or s.category_id in "
        "  (select id from categories where slug in ('leak', 'darkweb-sale')))"
    ), {"chats": [c.lower() for c in _leak_chats()]})

    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind in ('organisation', 'domain', 'brand', 'product', 'person')", name="ck_watchlist_kind"),
        sa.UniqueConstraint("kind", "name", name="uq_watchlist_kind_name"),
    )
    seen: set[str] = set()
    for word in _keywords():
        key = word.strip().lower()
        if not key or key in seen or _is_place(key):
            continue
        seen.add(key)
        kind, name, aliases, notes = KNOWN.get(key, ("organisation", key.title(), [key], ""))
        conn.execute(sa.text(
            "insert into watchlist (kind, name, aliases, country, notes) values (:kind, :name, :aliases, 'UZ', :notes) "
            "on conflict (kind, name) do nothing"
        ), {"kind": kind, "name": name, "aliases": aliases,
            "notes": ("TG_EXTRA_KEYWORDS dan (0018). " + notes).strip()})

    op.create_table(
        "publisher_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("weights", postgresql.JSONB(), nullable=False),
        sa.Column("bands", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_publisher_settings_single"),
    )
    conn.execute(sa.text(
        "insert into publisher_settings (id, weights, bands) values (1, cast(:w as jsonb), cast(:b as jsonb))"
    ), {"w": json.dumps(WEIGHTS), "b": json.dumps(BANDS)})


def downgrade() -> None:
    op.drop_table("publisher_settings")
    op.drop_table("watchlist")
    op.drop_constraint("ck_sources_reliability", "sources", type_="check")
    op.drop_column("sources", "reliability")
    op.drop_constraint("ck_events_priority_band", "events", type_="check")
    op.drop_index("ix_events_priority_band", table_name="events")
    op.drop_index("ix_events_priority", table_name="events")
    op.drop_column("events", "priority_reasons")
    op.drop_column("events", "priority_band")
    op.drop_column("events", "priority")
