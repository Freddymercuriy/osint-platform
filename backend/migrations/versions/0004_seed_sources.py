"""Manbalarni bazaga ko'chirish (v1 dagi feeds.FEEDS, 63 ta) va mavjud hodisalarni yangi ustunlarga o'tkazish

- sources: FEEDS dan bir xil bayroqlar bilan; interval_seconds = max(ttl, min_interval).
  Ro'yxat shu faylda muzlatilgan (kod keyin o'zgarsa ham migratsiya natijasi o'zgarmaydi).
- events: summary boshidagi "🔎 a, b · " → matched_keywords; channel; source_id (nom bo'yicha);
  countries (matndan); ransomware/leak → category_id va severity.
  Downgrade "🔎" prefiksini summary ga qaytaradi.

Revision ID: 0004_seed_sources
Revises: 0003_v2_data_model
Create Date: 2026-11-14
"""
import json
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_seed_sources"
down_revision: str | None = "0003_v2_data_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (name, kind, config, lang, fixed category slug, region_filter, cyber_filter, interval_seconds, enabled)
SOURCES = [
    ('ransomware.live', 'ransomware_live', {'countries': ['UZ', 'KZ', 'KG', 'TJ', 'TM']}, 'en', 'ransomware', False, False, 900, True),
    ('Gazeta.uz (UZ)', 'rss', {'url': 'https://www.gazeta.uz/uz/rss/'}, 'uz', None, False, True, 600, True),
    ('Gazeta.uz (RU)', 'rss', {'url': 'https://www.gazeta.uz/ru/rss/'}, 'ru', None, False, True, 600, True),
    ('Kun.uz (UZ)', 'rss', {'url': 'https://kun.uz/uz/news/rss'}, 'uz', None, False, True, 600, True),
    ('Kun.uz (RU)', 'rss', {'url': 'https://kun.uz/ru/news/rss'}, 'ru', None, False, True, 600, True),
    ('Spot.uz (RU)', 'rss', {'url': 'https://www.spot.uz/ru/rss/'}, 'ru', None, False, True, 600, True),
    ('Spot.uz (UZ)', 'rss', {'url': 'https://www.spot.uz/rss/'}, 'uz', None, False, True, 600, True),
    ('Daryo.uz (UZ)', 'rss', {'url': 'https://daryo.uz/feed/'}, 'uz', None, False, True, 600, True),
    ('Daryo.uz (RU)', 'rss', {'url': 'https://daryo.uz/ru/feed/'}, 'ru', None, False, True, 600, True),
    ('UzDaily (EN)', 'rss', {'url': 'https://uzdaily.uz/en/rss'}, 'en', None, False, True, 600, True),
    ('UzDaily (RU)', 'rss', {'url': 'https://uzdaily.uz/ru/rss'}, 'ru', None, False, True, 600, True),
    ('Nuz.uz', 'rss', {'url': 'https://nuz.uz/feed/'}, 'ru', None, False, True, 600, True),
    ('UZCERT', 'rss', {'url': 'https://uzcert.uz/rss'}, 'uz', None, False, False, 600, True),
    ('Tengrinews.kz', 'rss', {'url': 'https://tengrinews.kz/news.rss'}, 'ru', None, False, True, 600, True),
    ('Kursiv.media (KZ)', 'rss', {'url': 'https://kz.kursiv.media/feed/'}, 'ru', None, False, True, 600, True),
    ('Profit.kz', 'rss', {'url': 'https://profit.kz/rss/'}, 'ru', None, False, True, 600, True),
    ('DigitalBusiness.kz', 'rss', {'url': 'https://digitalbusiness.kz/feed/'}, 'ru', None, False, True, 600, True),
    ('Sputnik Казахстан', 'rss', {'url': 'https://sputnik.kz/export/rss2/archive/index.xml'}, 'ru', None, False, True, 600, True),
    ('24.kg', 'rss', {'url': 'https://24.kg/rss/'}, 'ru', None, False, True, 600, True),
    ('Kaktus.media', 'rss', {'url': 'https://kaktus.media/?rss'}, 'ru', None, False, True, 600, True),
    ('AKIpress', 'rss', {'url': 'https://akipress.com/rss/news.rss'}, 'en', None, False, True, 600, True),
    ('Kloop.kg', 'rss', {'url': 'https://kloop.kg/feed/'}, 'ru', None, False, True, 600, True),
    ('Kabar.kg', 'rss', {'url': 'https://kabar.kg/rss/'}, 'ru', None, False, True, 600, True),
    ('Sputnik Кыргызстан', 'rss', {'url': 'https://ru.sputnik.kg/export/rss2/archive/index.xml'}, 'ru', None, False, True, 600, True),
    ('Asia-Plus (RU)', 'rss', {'url': 'https://asiaplustj.info/ru/rss'}, 'ru', None, False, True, 600, True),
    ('Asia-Plus (EN)', 'rss', {'url': 'https://asiaplustj.info/en/rss'}, 'en', None, False, True, 600, True),
    ('Sputnik Таджикистан', 'rss', {'url': 'https://tj.sputniknews.ru/export/rss2/archive/index.xml'}, 'ru', None, False, True, 600, True),
    ('Turkmen.news', 'rss', {'url': 'https://turkmen.news/feed/'}, 'ru', None, False, True, 600, True),
    ('Хроника Туркменистана', 'rss', {'url': 'https://www.hronikatm.com/feed/'}, 'ru', None, False, True, 600, True),
    ('CentralAsia.media', 'rss', {'url': 'https://centralasia.media/rss'}, 'ru', None, False, True, 600, True),
    ('The Hacker News', 'rss', {'url': 'https://feeds.feedburner.com/TheHackersNews'}, 'en', None, True, False, 900, True),
    ('SecurityWeek', 'rss', {'url': 'https://www.securityweek.com/feed/'}, 'en', None, True, False, 900, True),
    ('The Record', 'rss', {'url': 'https://therecord.media/feed'}, 'en', None, True, False, 900, True),
    ('DataBreaches.net', 'rss', {'url': 'https://databreaches.net/feed/'}, 'en', None, True, False, 900, True),
    ('Securelist', 'rss', {'url': 'https://securelist.com/feed'}, 'en', None, True, False, 900, True),
    ('Securelist (RU)', 'rss', {'url': 'https://securelist.ru/feed/'}, 'ru', None, True, False, 900, True),
    ('Security Affairs', 'rss', {'url': 'https://securityaffairs.com/feed'}, 'en', None, True, False, 900, True),
    ('HackRead', 'rss', {'url': 'https://hackread.com/feed/'}, 'en', None, True, False, 900, True),
    ('Krebs on Security', 'rss', {'url': 'https://krebsonsecurity.com/feed/'}, 'en', None, True, False, 900, True),
    ('Dark Reading', 'rss', {'url': 'https://www.darkreading.com/rss.xml'}, 'en', None, True, False, 900, True),
    ('Help Net Security', 'rss', {'url': 'https://www.helpnetsecurity.com/feed/'}, 'en', None, True, False, 900, True),
    ('Infosecurity Magazine', 'rss', {'url': 'https://www.infosecurity-magazine.com/rss/news/'}, 'en', None, True, False, 900, True),
    ('The Register (Security)', 'rss', {'url': 'https://www.theregister.com/security/headlines.atom'}, 'en', None, True, False, 900, True),
    ('CyberScoop', 'rss', {'url': 'https://cyberscoop.com/feed/'}, 'en', None, True, False, 900, True),
    ('WeLiveSecurity (ESET)', 'rss', {'url': 'https://www.welivesecurity.com/en/rss/feed/'}, 'en', None, True, False, 900, True),
    ('Cisco Talos', 'rss', {'url': 'https://blog.talosintelligence.com/rss/'}, 'en', None, True, False, 900, True),
    ('Bitdefender Labs', 'rss', {'url': 'https://www.bitdefender.com/blog/api/rss/labs/'}, 'en', None, True, False, 900, True),
    ('Malwarebytes', 'rss', {'url': 'https://www.malwarebytes.com/blog/feed/index.xml'}, 'en', None, True, False, 900, True),
    ('SANS ISC', 'rss', {'url': 'https://isc.sans.edu/rssfeed.xml'}, 'en', None, True, False, 900, True),
    ('Xakep.ru', 'rss', {'url': 'https://xakep.ru/feed/'}, 'ru', None, True, False, 900, True),
    ('SecurityLab.ru', 'rss', {'url': 'https://www.securitylab.ru/_services/export/rss/'}, 'ru', None, True, False, 900, True),
    ('Anti-Malware.ru', 'rss', {'url': 'https://www.anti-malware.ru/news/feed'}, 'ru', None, True, False, 900, True),
    ('Habr: Информационная безопасность', 'rss', {'url': 'https://habr.com/ru/rss/hub/infosecurity/all/'}, 'ru', None, True, False, 900, True),
    ('Kaspersky Daily (RU)', 'rss', {'url': 'https://www.kaspersky.ru/blog/feed/'}, 'ru', None, True, False, 900, True),
    ('BleepingComputer', 'google_news', {'query': 'site:bleepingcomputer.com (Uzbekistan OR Kazakhstan OR Kyrgyzstan OR Tajikistan OR Turkmenistan OR "Central Asia") when:7d'}, 'en', None, False, False, 1800, True),
    ('CyberNews', 'google_news', {'query': 'site:cybernews.com (Uzbekistan OR Kazakhstan OR Kyrgyzstan OR Tajikistan OR Turkmenistan OR "Central Asia") when:7d'}, 'en', None, False, False, 1800, True),
    ('The Cyber Express', 'google_news', {'query': 'site:thecyberexpress.com (Uzbekistan OR Kazakhstan OR Kyrgyzstan OR Tajikistan OR Turkmenistan OR "Central Asia") when:7d'}, 'en', None, False, False, 1800, True),
    ('Turkmenportal', 'google_news', {'query': 'site:turkmenportal.com (хакеры OR кибератака OR "утечка данных" OR взлом OR фишинг OR кибербезопасность) when:7d'}, 'ru', None, False, True, 1800, True),
    ('Google News (EN)', 'google_news', {'query': '(Uzbekistan OR Kazakhstan OR Kyrgyzstan OR Tajikistan OR Turkmenistan OR "Central Asia") (hackers OR cyberattack OR ransomware OR "data breach" OR "data leak" OR phishing OR malware) when:7d'}, 'en', None, False, True, 1800, True),
    ('Google News (RU)', 'google_news', {'query': '(Узбекистан OR Казахстан OR Кыргызстан OR Таджикистан OR Туркменистан) (хакеры OR кибератака OR "утечка данных" OR взлом OR фишинг OR кибербезопасность) when:7d'}, 'ru', None, False, True, 1800, True),
    ('Dark Web Informer', 'rss', {'url': 'https://darkwebinformer.com/rss/'}, 'en', 'leak', True, False, 900, True),
    ('Have I Been Pwned', 'rss', {'url': 'https://feeds.feedburner.com/HaveIBeenPwnedLatestBreaches'}, 'en', 'leak', True, False, 900, True),
    ('Telegram (akkaunt)', 'telegram_user', {}, 'uz', None, False, False, 300, True),
]

GOOGLE_NEWS_TAG = " (Google News)"
_PREFIX = re.compile(r"^🔎 (?P<kw>.*?) · (?P<rest>.*)$", re.S)
_CHANNEL = {"news": "news", "ransomware": "api", "telegram": "telegram_channel", "tg_group": "telegram_group"}

# Davlatlarni aniqlash (o'sha paytdagi feeds.COUNTRY_KEYWORDS ning muzlatilgan nusxasi)
_COUNTRY_STEMS = {
    "UZ": ("uzbek", "o'zbek", "узбек", "ўзбек", "ӯзбек", "tashkent", "toshkent", "ташкент", "тошкент",
           "samarkand", "samarqand", "самарканд", "самарқанд", "bukhara", "buxoro", "бухара", "бухоро",
           "andijan", "andijon", "андижан", "андижон", "namangan", "наманган", "fergana", "ferghana",
           "farg'ona", "фергана", "фарғона", "nukus", "нукус", "urgench", "urganch", "ургенч", "termez",
           "termiz", "термез", "kokand", "qo'qon", "коканд", "qoraqalpoq", "karakalpak", "каракалпак",
           "khorezm", "xorazm", "хорезм"),
    "KZ": ("kazakh", "kazakstan", "kazahstan", "qozoq", "qozog'", "қозоқ", "қозоғ", "казах", "қазақ",
           "astana", "астана", "nur-sultan", "нур-султан", "almaty", "алматы", "алма-ата", "shymkent",
           "шымкент", "chimkent", "чимкент", "karaganda", "караганд", "қарағанды", "aktobe", "актобе",
           "ақтөбе", "atyrau", "атырау", "aktau", "актау", "pavlodar", "павлодар", "kostanay", "костанай",
           "kyzylorda", "кызылорда", "oskemen", "усть-каменогорск"),
    "KG": ("kyrgyz", "kirghiz", "kirgiz", "qirg'iz", "киргиз", "кыргыз", "қирғиз", "қырғыз", "bishkek",
           "бишкек", "jalal-abad", "джалал-абад"),
    "TJ": ("tajik", "tadjik", "tojik", "таджик", "тоҷик", "тожик", "dushanbe", "душанбе", "khujand",
           "xo'jand", "худжанд", "хуҷанд", "khatlon", "хатлон"),
    "TM": ("turkmen", "turkman", "туркмен", "ashgabat", "ashkhabad", "ashgabad", "ашхабад", "ашгабат",
           "turkmenbashi", "dashoguz", "дашогуз"),
}
_APOS = "['\u2018\u2019\u02bb\u02bc`]?"
_COUNTRY_RX = {
    code: re.compile(
        "|".join(r"(?<!\w)" + re.escape(s).replace("'", _APOS) for s in stems)
        + rf"|(?<=[a-z\-])\.{code.lower()}(?![\w\-])",
        re.IGNORECASE,
    )
    for code, stems in _COUNTRY_STEMS.items()
}


def _countries(text: str) -> list[str]:
    flat = re.sub(r"\s+", " ", text or "")
    return [code for code, rx in _COUNTRY_RX.items() if rx.search(flat)]


def upgrade() -> None:
    conn = op.get_bind()
    cats = dict(conn.execute(sa.text("select slug, id from categories")).all())
    sev = dict(conn.execute(sa.text("select slug, severity from categories")).all())

    insert = sa.text(
        "insert into sources (name, kind, config, lang, category_id, scope, region_filter, cyber_filter, "
        "interval_seconds, enabled, api_key_env, notes) values (:name, :kind, cast(:config as jsonb), :lang, "
        ":category_id, 'regional', :rf, :cf, :interval, :enabled, null, '')"
    )
    for name, kind, config, lang, fixed, rf, cf, interval, enabled in SOURCES:
        conn.execute(insert, dict(name=name, kind=kind, config=json.dumps(config, ensure_ascii=False), lang=lang,
                                  category_id=cats.get(fixed) if fixed else None, rf=rf, cf=cf,
                                  interval=interval, enabled=enabled))
    sources = {n: (i, k) for i, n, k in conn.execute(sa.text("select id, name, kind from sources")).all()}
    tg_source = next((i for n, (i, k) in sources.items() if k == "telegram_user"), None)

    rows = conn.execute(sa.text("select id, source, category, title, summary from events")).all()
    update = sa.text(
        "update events set summary = :summary, matched_keywords = :kw, channel = :channel, source_id = :sid, "
        "countries = :countries, category_id = :cid, severity = :sev where id = :id"
    )
    for eid, source, category, title, summary in rows:
        kw: list[str] = []
        m = _PREFIX.match(summary or "")
        if m:
            kw = [k.strip() for k in m.group("kw").split(",") if k.strip()]
            summary = m.group("rest")
        is_tg = source.startswith("TG: ")
        channel = _CHANNEL.get(category) or ("telegram_channel" if is_tg else "news")
        sid = None
        if source in sources:
            sid = sources[source][0]
        elif source.endswith(GOOGLE_NEWS_TAG) and source[: -len(GOOGLE_NEWS_TAG)] in sources:
            sid = sources[source[: -len(GOOGLE_NEWS_TAG)]][0]
        elif is_tg:
            sid = tg_source
        conn.execute(update, dict(
            id=eid, summary=summary, kw=kw, channel=channel, sid=sid,
            countries=_countries(f"{title} {summary}"),
            cid=cats.get(category), sev=sev.get(category, "info"),
        ))


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("select id, summary, matched_keywords from events")).all()
    for eid, summary, kw in rows:
        if kw:
            conn.execute(sa.text("update events set summary = :s where id = :id"),
                         dict(id=eid, s=f"🔎 {', '.join(kw)} · {summary}"))
    conn.execute(sa.text(
        "update events set source_id = null, category_id = null, matched_keywords = '{}', countries = '{}'"
    ))
    conn.execute(sa.text("delete from sources"))
