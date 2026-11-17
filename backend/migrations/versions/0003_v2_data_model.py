"""v2 ma'lumot modeli: categories, sources, source_runs; events ga yangi ustunlar; 15 kategoriya

Revision ID: 0003_v2_data_model
Revises: 0002_user_roles
Create Date: 2026-11-14
"""
import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0003_v2_data_model"
down_revision: str | None = "0002_user_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)

# (slug, en, ru, uz, severity, color, icon, sort, is_system, description en / ru / uz)
CATEGORIES = [
    ("ransomware", "Ransomware", "Программы-вымогатели", "To'lov talab qiluvchi dasturlar (ransomware)",
     "critical", "red", "Skull", 10, True,
     "Organisations listed on ransomware leak sites or hit by ransomware.",
     "Организации на сайтах утечек вымогателей или пострадавшие от шифровальщиков.",
     "Ransomware guruhlari sizdirish saytiga qo'ygan yoki shifrlovchi dastur hujumiga uchragan tashkilotlar."),
    ("leak", "Data breaches & leaks", "Утечки данных", "Ma'lumotlar sizib chiqishi",
     "high", "orange", "DatabaseZap", 20, True,
     "Databases and personal data exposed or stolen.",
     "Раскрытые или похищенные базы и персональные данные.",
     "Ochiq qolgan yoki o'g'irlangan bazalar va shaxsiy ma'lumotlar."),
    ("darkweb-sale", "Dark web sales", "Продажа в даркнете", "Darknetda sotuv",
     "high", "purple", "ShoppingCart", 30, False,
     "Network access and databases offered for sale.",
     "Продажа доступов к сетям и баз данных.",
     "Tarmoqqa kirish huquqi va bazalarni sotuvga qo'yish."),
    ("credentials", "Stolen credentials & infostealers", "Украденные учётные данные и стилеры",
     "O'g'irlangan login-parollar va stealerlar",
     "high", "pink", "KeyRound", 40, False,
     "Leaked logins, infostealer logs and account takeovers.",
     "Утёкшие логины, логи стилеров и захват аккаунтов.",
     "Sizib chiqqan loginlar, stealer loglari va akkauntlarni egallash."),
    ("phishing", "Phishing", "Фишинг", "Fishing",
     "medium", "amber", "Fish", 50, False,
     "Fake sites, messages and links that steal logins or money.",
     "Поддельные сайты, сообщения и ссылки для кражи логинов и денег.",
     "Login yoki pulni o'g'irlaydigan soxta sayt, xabar va havolalar."),
    ("fraud", "Online & financial fraud", "Онлайн- и финансовое мошенничество", "Onlayn va moliyaviy firibgarlik",
     "medium", "yellow", "Banknote", 60, False,
     "Online scams, card fraud and account theft.",
     "Интернет-мошенничество, кража с карт и аккаунтов.",
     "Internet firibgarligi, karta va akkauntlardan o'g'irlik."),
    ("malware", "Malware", "Вредоносное ПО", "Zararli dasturlar",
     "high", "rose", "Bug", 70, False,
     "Viruses, trojans, botnets and malicious apps.",
     "Вирусы, трояны, ботнеты и вредоносные приложения.",
     "Viruslar, troyanlar, botnetlar va zararli ilovalar."),
    ("vulnerability", "Vulnerabilities", "Уязвимости", "Zaifliklar",
     "medium", "sky", "ShieldAlert", 80, True,
     "Security flaws in software and devices, including those exploited in the wild.",
     "Уязвимости в программах и устройствах, в том числе эксплуатируемые.",
     "Dastur va qurilmalardagi xavfsizlik kamchiliklari, jumladan faol ishlatilayotganlari."),
    ("ddos-outage", "DDoS & outages", "DDoS и сбои", "DDoS va uzilishlar",
     "medium", "indigo", "ServerCrash", 90, False,
     "Denial-of-service attacks and internet or service outages.",
     "DDoS-атаки и сбои интернета или сервисов.",
     "DDoS hujumlari, internet yoki xizmatlardagi uzilishlar."),
    ("defacement", "Defacement & hacktivism", "Дефейс и хактивизм", "Deface va xaktivizm",
     "medium", "lime", "Flag", 100, False,
     "Hacked website front pages and politically motivated attacks.",
     "Взлом главных страниц сайтов и политически мотивированные атаки.",
     "Sayt bosh sahifasini buzish va siyosiy maqsadli hujumlar."),
    ("espionage", "Espionage & APT", "Шпионаж и APT", "Josuslik va APT",
     "high", "violet", "Eye", 110, False,
     "State-backed hacking groups and spyware.",
     "Государственные хакерские группы и шпионское ПО.",
     "Davlat qo'llab-quvvatlaydigan xaker guruhlari va josuslik dasturlari."),
    ("law-enforcement", "Arrests & takedowns", "Задержания и ликвидации", "Hibsga olish va bloklash",
     "low", "green", "Gavel", 120, False,
     "Police actions against cybercriminals and infrastructure takedowns.",
     "Задержания киберпреступников и ликвидация их инфраструктуры.",
     "Kiberjinoyatchilarni ushlash va ularning infratuzilmasini yopish."),
    ("advisory", "Regulation & official warnings", "Регулирование и официальные предупреждения",
     "Qonunchilik va rasmiy ogohlantirishlar",
     "info", "teal", "Megaphone", 130, False,
     "Laws, regulators and official security warnings.",
     "Законы, регуляторы и официальные предупреждения.",
     "Qonunlar, regulyatorlar va rasmiy xavfsizlik ogohlantirishlari."),
    ("research", "Threat research", "Исследования угроз", "Tahdidlar tadqiqoti",
     "info", "cyan", "FlaskConical", 140, False,
     "Reports and analysis from security researchers.",
     "Отчёты и аналитика исследователей безопасности.",
     "Xavfsizlik tadqiqotchilarining hisobot va tahlillari."),
    ("other", "Other", "Другое", "Boshqa",
     "info", "slate", "CircleDashed", 1000, True,
     "Security news that fits no other category.",
     "Новости безопасности вне других категорий.",
     "Boshqa kategoriyalarga kirmaydigan xavfsizlik yangiliklari."),
]


def _env_list(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(48), nullable=False, unique=True),
        sa.Column("name_en", sa.String(96), nullable=False),
        sa.Column("name_ru", sa.String(96), nullable=False),
        sa.Column("name_uz", sa.String(96), nullable=False),
        sa.Column("description_en", sa.Text(), server_default="", nullable=False),
        sa.Column("description_ru", sa.Text(), server_default="", nullable=False),
        sa.Column("description_uz", sa.Text(), server_default="", nullable=False),
        sa.Column("severity", sa.String(16), server_default="info", nullable=False),
        sa.Column("color", sa.String(32), server_default="slate", nullable=False),
        sa.Column("icon", sa.String(48), server_default="Tag", nullable=False),
        sa.Column("notify", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="100", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("rules", pg.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("severity in ('info', 'low', 'medium', 'high', 'critical')",
                           name="ck_categories_severity"),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("config", pg.JSONB(), server_default="{}", nullable=False),
        sa.Column("lang", sa.String(8), server_default="en", nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scope", sa.String(16), server_default="regional", nullable=False),
        sa.Column("region_filter", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("cyber_filter", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("translate", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("interval_seconds", sa.Integer(), server_default="900", nullable=False),
        sa.Column("jitter_pct", sa.Integer(), server_default="20", nullable=False),
        sa.Column("backfill_days", sa.Integer(), server_default="14", nullable=False),
        sa.Column("api_key_env", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("etag", sa.String(256), nullable=True),
        sa.Column("last_modified", sa.String(64), nullable=True),
        sa.Column("next_run_at", _TS, nullable=True),
        sa.Column("state", pg.JSONB(), server_default="{}", nullable=False),
        sa.Column("baseline_done", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(16), server_default="never_run", nullable=False),
        sa.Column("last_check_at", _TS, nullable=True),
        sa.Column("last_success_at", _TS, nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_http_status", sa.Integer(), nullable=True),
        sa.Column("last_latency_ms", sa.Integer(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_items", sa.Integer(), nullable=True),
        sa.Column("last_new_items", sa.Integer(), nullable=True),
        sa.Column("newest_item_at", _TS, nullable=True),
        sa.Column("down_since", _TS, nullable=True),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("scope in ('regional', 'global')", name="ck_sources_scope"),
        sa.CheckConstraint(
            "status in ('ok', 'degraded', 'down', 'blocked', 'auth_missing', 'disabled', 'never_run')",
            name="ck_sources_status",
        ),
        sa.CheckConstraint("interval_seconds >= 60", name="ck_sources_interval"),
        sa.CheckConstraint("jitter_pct between 0 and 90", name="ck_sources_jitter"),
    )
    op.create_index("ix_sources_due", "sources", ["enabled", "next_run_at"])

    op.create_table(
        "source_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", _TS, nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("new_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("manual", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index("ix_source_runs_source_started", "source_runs", ["source_id", "started_at"])
    op.create_index("ix_source_runs_started_at", "source_runs", ["started_at"])

    # --- events: yangi ustunlar
    op.alter_column("events", "category", type_=sa.String(48), existing_nullable=False)
    op.alter_column("events", "summary", server_default="", existing_nullable=False)
    op.add_column("events", sa.Column("source_id", sa.Integer(),
                                      sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True))
    op.add_column("events", sa.Column("category_id", sa.Integer(),
                                      sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True))
    op.add_column("events", sa.Column("category_locked", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("events", sa.Column("channel", sa.String(24), server_default="news", nullable=False))
    op.add_column("events", sa.Column("scope", sa.String(16), server_default="regional", nullable=False))
    op.add_column("events", sa.Column("severity", sa.String(16), server_default="info", nullable=False))
    op.add_column("events", sa.Column("countries", pg.ARRAY(sa.String(2)), server_default=sa.text("'{}'"),
                                      nullable=False))
    op.add_column("events", sa.Column("sector", sa.String(32), nullable=True))
    op.add_column("events", sa.Column("actor", sa.String(128), nullable=True))
    op.add_column("events", sa.Column("matched_keywords", pg.ARRAY(sa.Text()), server_default=sa.text("'{}'"),
                                      nullable=False))
    op.add_column("events", sa.Column("extra", pg.JSONB(), server_default="{}", nullable=False))
    op.add_column("events", sa.Column("also_reported_by", pg.JSONB(), server_default="[]", nullable=False))
    op.add_column("events", sa.Column("is_baseline", sa.Boolean(), server_default="false", nullable=False))
    op.create_index("ix_events_countries", "events", ["countries"], postgresql_using="gin")
    op.create_index("ix_events_category_id", "events", ["category_id"])
    op.create_index("ix_events_source_id", "events", ["source_id"])

    # --- 15 kategoriya. notify / retention_days — muhit qiymatlaridan BIR MARTA (keyin admin panelida)
    notify = set(_env_list("NOTIFY_CATEGORIES", "leak,ransomware"))
    keep = set(_env_list("EVENTS_RETENTION_KEEP", "ransomware,leak"))
    days = int(os.environ.get("EVENTS_RETENTION_DAYS", "90") or 0)
    table = sa.table(
        "categories",
        *(sa.column(c) for c in (
            "slug", "name_en", "name_ru", "name_uz", "description_en", "description_ru", "description_uz",
            "severity", "color", "icon", "notify", "retention_days", "sort_order", "is_system",
        )),
    )
    op.bulk_insert(table, [
        dict(slug=slug, name_en=en, name_ru=ru, name_uz=uz, severity=sev, color=color, icon=icon,
             sort_order=sort, is_system=system, description_en=den, description_ru=dru, description_uz=duz,
             notify=slug in notify, retention_days=None if (slug in keep or days <= 0) else days)
        for slug, en, ru, uz, sev, color, icon, sort, system, den, dru, duz in CATEGORIES
    ])


def downgrade() -> None:
    op.drop_index("ix_events_source_id", "events")
    op.drop_index("ix_events_category_id", "events")
    op.drop_index("ix_events_countries", "events")
    for col in ("is_baseline", "also_reported_by", "extra", "matched_keywords", "actor", "sector", "countries",
                "severity", "scope", "channel", "category_locked", "category_id", "source_id"):
        op.drop_column("events", col)
    op.alter_column("events", "summary", server_default=None, existing_nullable=False)
    op.alter_column("events", "category", type_=sa.String(32), existing_nullable=False)
    op.drop_table("source_runs")
    op.drop_table("sources")
    op.drop_table("categories")
