"""Yangi threat-intel manbalari (Bosqich 3) va milliy CERT'lar

Kalit talab qiladigan manba kalit sozlanmagan bo'lsa — o'chiq, holati `auth_missing` (kalit `backend/.env` ga
qo'shilib, admin panelda yoqiladi). Kalit migratsiya paytida bor bo'lsa — yoqiq.
Bloklangan saytlar (CAPTCHA / 403) — o'chiq, holati `blocked`, izohda sabab; ular Google News orqali kuzatiladi.
HIBP RSS — HIBP API (`hibp_breaches`) bilan almashtirildi (o'chiriladi). UZCERT — standart davlat UZ.

Revision ID: 0007_threat_intel_sources
Revises: 0006_telegram_sources
Create Date: 2026-11-14
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_threat_intel_sources"
down_revision: str | None = "0006_telegram_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CA = ["UZ", "KZ", "KG", "TJ", "TM"]
KEV_URL = "https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json"
# OpenPhish uchun aniq brendlar (TG_EXTRA_KEYWORDS dagi umumiy so'zlar — "egov", shaharlar — global lentada
# yolg'on mos kelish beradi). Milliy domendagi (.uz .kz ...) URL'lar brenddan qat'i nazar olinadi.
BRANDS = ["uzcard", "humo", "payme", "ucell", "uztelecom", "uzmobile", "mobiuz", "kapitalbank", "agrobank",
          "hamkorbank", "ipotekabank", "xalqbank", "uzum", "soliq", "kaspi", "halykbank", "halyk", "jusan",
          "kcell", "kazpost", "mbank", "optimabank", "bakai", "megacom", "eskhata", "tcell", "tmcell"]
KG_CERT = {"url": "https://cert.gov.kg/ru/news/", "item": "a.news-pages-card", "title": ".news-title",
           "link": ".", "date": ".news-data-text", "date_format": "auto", "summary": ".main-text",
           "default_countries": ["KG"]}

# (name, kind, config, lang, category, scope, interval, backfill, key_env, key_required, enabled, status, notes)
SOURCES = [
    ("ransomware.live PRO", "ransomware_live_pro", {"countries": CA}, "en", "ransomware", "regional", 1800, 30,
     "RANSOMWARE_LIVE_API_KEY", True, True, None,
     "PRO API (bepul shaxsiy kalit). Legacy v2 manbasi zaxira sifatida yoqiq qoladi; takrorlar birlashadi."),
    ("RansomLook", "ransomlook", {"countries": CA, "limit": 100}, "en", "ransomware", "regional", 1800, 30,
     None, False, True, None, "Ikkinchi leak-site kuzatuvchi (ransomware.live bilan solishtirish)."),
    ("Have I Been Pwned (breaches API)", "hibp_breaches", {}, "en", "leak", "global", 21600, 14,
     None, False, True, None, "HIBP RSS o'rniga. Element scope'i domen/matnga qarab regional yoki global."),
    ("CISA KEV", "cisa_kev", {"url": KEV_URL}, "en", "vulnerability", "global", 7200, 30,
     None, False, True, None, "cisagov/kev-data GitHub ko'zgusi (cisa.gov bu tarmoqdan 403 bergan)."),
    ("NVD critical CVEs", "nvd_cves", {}, "en", "vulnerability", "global", 7200, 7,
     "NVD_API_KEY", False, False, "disabled", "Shovqinli — ataylab o'chiq. Kalitsiz 5 so'rov / 30 s."),
    ("abuse.ch URLhaus (CA)", "urlhaus", {}, "en", "malware", "regional", 3600, 3,
     "ABUSECH_AUTH_KEY", True, True, None, "Faqat .uz .kz .kg .tj .tm xostlar."),
    ("abuse.ch ThreatFox (CA)", "threatfox", {}, "en", "malware", "regional", 3600, 7,
     "ABUSECH_AUTH_KEY", True, True, None, "Faqat mintaqa domenlari / API ko'rsatgan davlat."),
    ("OpenPhish community feed", "openphish", {"brands": BRANDS}, "en", "phishing", "regional", 21600, 3,
     None, False, True, None, "Mintaqa domenlari yoki config.brands dagi brend nomlari."),
    ("LevelBlue OTX pulses (Central Asia)", "otx_pulses", {"countries": CA, "limit": 50, "max_pages": 5}, "en",
     None, "regional", 3600, 14, "OTX_API_KEY", True, True, None, "pulses/subscribed — mintaqani tilga olganlari."),
    ("Cloudflare Radar outages", "cloudflare_radar", {"countries": CA}, "en", "ddos-outage", "regional", 3600, 14,
     "CLOUDFLARE_API_TOKEN", True, True, None, "Internet uzilishlari (annotations/outages)."),
    ("KG-CERT (KCOKB)", "html_list", KG_CERT, "ru", None, "regional", 21600, 365,
     None, False, True, None, "RSS yo'q — yangiliklar sahifasi (server-rendered). Kam yangilanadi."),
    ("CERT.TJ", "rss", {"url": "https://cert.tj/?feed=rss2", "default_countries": ["TJ"]}, "ru", None, "regional",
     21600, 365, None, False, False, "disabled", "Lentada faqat WordPress namunasi (2024) — keyin qayta tekshirish."),
    ("Kazakhstan STS (sts.kz)", "html_list",
     {"url": "https://sts.kz/ru/news", "item": "a[href*='/ru/news/']", "title": "self", "link": "self",
      "date": "time", "default_countries": ["KZ"]}, "ru", None, "regional", 21600, 30,
     None, False, False, "blocked", "Bir necha so'rovdan keyin 'Firewall Captcha' — chetlab o'tilmaydi. "
     "Google News orqali kuzatiladi."),
    ("KZ-CERT (kz-cert.kz)", "rss", {"url": "https://kz-cert.kz/", "default_countries": ["KZ"]}, "ru", None,
     "regional", 21600, 30, None, False, False, "blocked",
     "HTTP 403. cert.gov.kz — JS ilova, ochiq lenta yo'q (hujjatlanmagan ichki JSON ishlatilmaydi). "
     "Google News orqali kuzatiladi."),
    ("Google News: KZ-CERT / STS", "google_news",
     {"query": '("KZ-CERT" OR "cert.gov.kz" OR "Служба технической безопасности" OR "КЦОКБ" OR "cert.gov.kg") '
               "when:14d", "default_countries": ["KZ"]}, "ru", None, "regional", 3600, 14,
     None, False, True, None, "Bloklangan / lentasiz CERT saytlari uchun ikkilamchi manba."),
]


def _key_set(env: str | None) -> bool:
    if not env:
        return False
    import os

    from app.core.config import settings

    return bool(os.environ.get(env) or getattr(settings, env.lower(), None))


def upgrade() -> None:
    conn = op.get_bind()
    cats = dict(conn.execute(sa.text("select slug, id from categories")).all())
    for (name, kind, config, lang, cat, scope, interval, backfill, key_env, key_required, enabled, status,
         notes) in SOURCES:
        if key_required and not _key_set(key_env):
            enabled, status = False, "auth_missing"
        status = status or ("never_run" if enabled else "disabled")
        conn.execute(sa.text(
            "insert into sources (name, kind, config, lang, category_id, scope, interval_seconds, backfill_days, "
            "api_key_env, enabled, status, notes) values (:name, :kind, cast(:config as jsonb), :lang, :cat, :scope, "
            ":interval, :backfill, :key_env, :enabled, :status, :notes) on conflict (name) do nothing"
        ), dict(name=name, kind=kind, config=json.dumps(config, ensure_ascii=False), lang=lang,
                cat=cats.get(cat) if cat else None, scope=scope, interval=interval, backfill=backfill,
                key_env=key_env, enabled=enabled, status=status, notes=notes))
    conn.execute(sa.text(
        "update sources set enabled = false, status = 'disabled', next_run_at = null, "
        "notes = 'HIBP API (hibp_breaches) bilan almashtirildi' where name = 'Have I Been Pwned' and kind = 'rss'"
    ))
    conn.execute(sa.text(
        "update sources set config = config || '{\"default_countries\": [\"UZ\"]}'::jsonb where name = 'UZCERT'"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("delete from sources where name = any(:names)"), {"names": [s[0] for s in SOURCES]})
    conn.execute(sa.text(
        "update sources set enabled = true, status = 'never_run', notes = '' "
        "where name = 'Have I Been Pwned' and kind = 'rss'"
    ))
    conn.execute(sa.text("update sources set config = config - 'default_countries' where name = 'UZCERT'"))
