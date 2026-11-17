"""Kategoriya qoidalari (15 ta) va eski hodisalarni qayta tasniflash

Boshlang'ich qoidalar `feeds.TOPIC_STEMS`, `feeds.TOPIC_PATTERNS` va `dedup._TOPICS` asosida tuzilgan va shu yerda
muzlatilgan; keyin admin panelida tahrirlanadi.
- Eski `ransomware` va `leak` hodisalari kategoriyasini saqlaydi (`extra.fixed_category`).
- Eski `news`, `telegram`, `tg_group` hodisalari qoidalar bilan tasniflanadi (kanal Bosqich 1 da qo'yilgan).

Revision ID: 0008_category_rules
Revises: 0007_threat_intel_sources
Create Date: 2026-11-14
"""
import json
from collections.abc import Sequence
from types import SimpleNamespace

import sqlalchemy as sa
from alembic import op

revision: str = "0008_category_rules"
down_revision: str | None = "0007_threat_intel_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DATA_LEAK_EN = (r"(?:data|database|records|credentials|passwords?|personal (?:data|information)|customer data|"
                 r"user data)\W+(?:\w+\W+){0,3}(?:leak|breach|exposed|stolen|compromised|dumped|for sale|sold)")
_DATA_LEAK_RU = (r"(?:данн\w*|баз\w*|информаци\w*|пароли|сведени\w*|аккаунт\w*|документ\w*)\W+(?:\w+\W+){0,3}"
                 r"(?:утек|утечк|слит|слили|слив|украден|похищен|скомпрометирован|в открытом доступе)")

RULES = {
    "ransomware": {
        "stems": {
            "en": ["ransomware", "ransom note", "ransom demand", "lockbit", "blackcat", "alphv", "akira", "cl0p",
                   "black basta", "rhysida", "qilin", "medusa ransomware", "play ransomware", "encrypted files"],
            "ru": ["вымогател", "шифровальщик", "рансомвар", "рэнсомвар", "выкуп"],
            "uz": ["to'lov talab qiluvchi", "tovlamachi dastur", "shifrlovchi dastur", "ransomware"],
        },
        "patterns": [r"(?:программ\w*|вирус\w*|троян\w*)[- ]вымогател"],
        "weight": 1.3,
    },
    "leak": {
        "stems": {
            "en": ["data breach", "data leak", "leaked", "leak ", "leaks ", "leak of", "breached", "exposed database",
                   "records exposed", "personal data", "accounts breached", "exposed data"],
            "ru": ["утечк", "утек", "утёк", "слив", "слили", "слит", "персональных данных", "персональные данные",
                   "в открытом доступе"],
            "uz": ["sizib chiq", "sizib ketgan", "sizdirilgan", "ma'lumotlar sizib", "shaxsiy ma'lumot", "oshkor bo'l"],
            "kk": ["деректер ағып", "жеке деректер"],
        },
        "patterns": [_DATA_LEAK_EN, _DATA_LEAK_RU,
                     r"(?:documents?|files|документ\w*|файл\w*|hujjat\w*)\W+(?:\w+\W+){0,6}"
                     r"(?:stolen|exfiltrated|похищен\w*|украден\w*|o'g'irlan\w*)",
                     r"(?:steal|stole|похитил\w*|украл\w*|o'g'irla\w*)\W+(?:\w+\W+){0,5}"
                     r"(?:documents?|files|data|документ\w*|данн\w*|hujjat\w*|ma'lumot\w*)"],
        "exclude": [r"утечк\w* (?:газа|нефти|воды|тепла|мозгов|кадров)"],
        "weight": 1.1,
    },
    "darkweb-sale": {
        "stems": {
            "en": ["for sale", "selling access", "sells access", "initial access", "access broker", "put up for sale",
                   "offered for sale", "dark web market"],
            "ru": ["выставил на продажу", "выставлен на продажу", "выставлены на продажу", "продают доступ",
                   "продажа доступ", "продаются", "продает базу", "продаёт базу", "брокер доступа"],
            "uz": ["sotuvga qo'y", "sotmoqda", "sotilmoqda", "sotuvga chiqar"],
        },
        "patterns": [r"(?:dark ?web|darknet|даркнет|дарквеб)\W+(?:\w+\W+){0,6}(?:sale|sold|продаж|продав|sotuv)",
                     r"(?:sale|sold|продаж|продав|sotuv)\w*\W+(?:\w+\W+){0,6}(?:dark ?web|darknet|даркнет|дарквеб)"],
        "weight": 1.2,
    },
    "credentials": {
        "stems": {
            "en": ["credential", "passwords", "password", "infostealer", "info-stealer", "stealer log", "stealer",
                   "logins", "account takeover", "credential stuffing", "combolist", "session cookies"],
            "ru": ["учетные данные", "учётные данные", "учетных записей", "учётных записей", "пароли", "паролей",
                   "стилер", "логины", "логинов", "взлом аккаунт", "угон аккаунт"],
            "uz": ["parol", "login va parol", "akkauntlarni o'g'irla", "akkaunti buzil", "akkauntini buz"],
        },
        "weight": 1.0,
    },
    "phishing": {
        "stems": {
            "en": ["phishing", "phish", "smishing", "vishing", "spoofed site", "fake website", "fake login",
                   "lookalike domain"],
            "ru": ["фишинг", "поддельн сайт", "поддельный сайт", "фейковый сайт", "фейковые сайт", "мошеннический сайт",
                   "мошеннические ссылк", "вредоносные ссылк"],
            "uz": ["fishing", "soxta sayt", "soxta havola", "yolg'on havola", "qalbaki sayt"],
            "kk": ["фишинг", "жалған сайт"],
        },
        "weight": 1.2,
    },
    "fraud": {
        "stems": {
            "en": ["fraud", "scam", "scammer", "money mule", "sim swap", "card fraud", "investment scam"],
            "ru": ["мошенн", "афер", "лжеброкер", "дропп", "обманом", "обманули", "списали деньги", "похитили деньги",
                   "украли деньги"],
            "uz": ["firibgar", "aldov", "aldab", "pul o'g'irla", "kartadan pul"],
            "kk": ["алаяқ"],
        },
        "weight": 1.0,
    },
    "malware": {
        "stems": {
            "en": ["malware", "trojan", "botnet", "backdoor", "spyware", "rootkit", "keylogger", "virus", "worm",
                   "loader", "remote access trojan", "malicious app", "malicious url", "c2 server"],
            "ru": ["вредонос", "троян", "ботнет", "бэкдор", "вирус", "зловред", "шпионское по", "вредоносное по"],
            "uz": ["zararli dastur", "zararli ilova", "virus", "troyan"],
            "kk": ["зиянды бағдарлама", "вирус"],
        },
        "exclude": [r"троянск\w* кон", r"trojan horse"],
        "weight": 1.0,
    },
    "vulnerability": {
        "stems": {
            "en": ["vulnerability", "vulnerabilities", "zero-day", "0-day", "exploit", "security update", "patch",
                   "remote code execution", "privilege escalation", "security flaw"],
            "ru": ["уязвим", "эксплойт", "эксплуатир", "нулевого дня", "обновлени безопасности", "исправлени",
                   "патч"],
            "uz": ["zaiflik", "zaifligi", "zaifliklar", "kod bajarish", "xavfsizlik yangilanish", "yangilanishlar orqali"],
            "kk": ["осалдық"],
        },
        "patterns": [r"cve-\d{4}-\d{3,}"],
        "weight": 1.1,
    },
    "ddos-outage": {
        "stems": {
            "en": ["ddos", "denial of service", "denial-of-service", "outage", "downtime", "service disruption",
                   "internet shutdown", "connectivity"],
            "ru": ["ddos", "ддос", "dos-атак", "сбой", "перебои", "недоступн", "отключение интернет"],
            "uz": ["ddos", "uzilish", "ishlamay qoldi", "internet o'chir", "ishdan chiqdi"],
            "kk": ["ddos", "іркіліс"],
        },
        "weight": 1.1,
    },
    "defacement": {
        "stems": {
            "en": ["defac", "hacktivis", "hacked website", "website was hacked", "hacked the website"],
            "ru": ["дефейс", "хактивист", "взломали сайт", "взлом сайта", "взломан сайт", "сайт был взломан",
                   "взломали официальный сайт"],
            "uz": ["saytini buz", "sayti buzil", "saytni buz", "deface", "xaktivist"],
        },
        "weight": 1.2,
    },
    "espionage": {
        "stems": {
            "en": ["espionage", "cyber-espionage", "cyberespionage", "spying", "spied", "spy ", "state-sponsored",
                   "nation-state", "apt group", "turla", "silent lynx", "apt28", "apt29", "sandworm", "lazarus",
                   "spyware campaign", "fsb ", "gru ", "intelligence service"],
            "ru": ["шпион", "кибершпион", "слежк", "госхакер", "проправительственн", "фсб ", "гру ", "спецслужб",
                   "разведк"],
            "uz": ["josus", "josuslik", "kuzatuv dasturi"],
            "kk": ["тыңшы"],
        },
        "patterns": [r"\bapt ?\d{1,2}\b", r"(?:hackers|хакер\w*)\W+(?:\w+\W+){0,3}(?:fsb|фсб|gru|гру|state|государств)",
                     r"(?:steal|stole|stolen|spy|похит\w*|украл\w*|шпион\w*)\W+(?:\w+\W+){0,6}"
                     r"(?:government|govt|state|national security|госорган\w*|секретн\w*|нацбезопасн\w*|"
                     r"национальной безопасност\w*|davlat)",
                     r"(?:government|govt|state|security|госорган\w*|секретн\w*|нацбезопасн\w*|"
                     r"национальной безопасност\w*)\W+(?:\w+\W+){0,4}(?:documents?|документ\w*)\W+(?:\w+\W+){0,4}"
                     r"(?:stolen|похищен\w*|украден\w*)"],
        "weight": 1.2,
    },
    "law-enforcement": {
        "stems": {
            "en": ["arrested", "arrest", "detained", "sentenced", "charged", "indicted", "takedown", "taken down",
                   "seized", "extradit", "convicted", "police raid"],
            "ru": ["задержан", "задержали", "арестован", "арест", "осужден", "осуждён", "приговор", "уголовное дело",
                   "возбудили дело", "ликвидир", "изъяли", "задержание"],
            "uz": ["hibsga olin", "qo'lga olin", "ushlandi", "ushlab qolin", "jinoyat ishi qo'zg'at", "sudlan",
                   "ozodlikdan mahrum", "fosh etildi"],
            "kk": ["ұсталды", "қамауға алын", "қылмыстық іс"],
        },
        "weight": 1.0,
    },
    "advisory": {
        "stems": {
            "en": ["advisory", "warns", "warning", "regulation", "regulator", "decree", "guidelines", "new law",
                   "requirements", "recommendations", "urges"],
            "ru": ["предупред", "предупрежд", "закон", "постановлени", "регулятор", "рекомендац", "указ ", "призыва",
                   "напомина", "требовани"],
            "uz": ["ogohlantir", "qonun", "qaror", "farmon", "tavsiya", "eslatma", "talablar"],
            "kk": ["ескерт", "заң", "ұсыным"],
        },
        "weight": 0.6,
    },
    "research": {
        "stems": {
            "en": ["report", "research", "researchers", "analysis", "threat intelligence", "study", "survey",
                   "statistics", "trends"],
            "ru": ["исследовани", "отчет", "отчёт", "аналитик", "эксперты", "статистик", "рейтинг", "обзор"],
            "uz": ["tadqiqot", "hisobot", "tahlil", "statistika", "mutaxassislar"],
            "kk": ["зерттеу", "есеп", "талдау"],
        },
        "weight": 0.5,
    },
}


def _classify_legacy(conn) -> None:
    from app.services.events.classifier import classify, compile_categories

    cats = [SimpleNamespace(slug=r.slug, rules=r.rules, severity=r.severity, sort_order=r.sort_order,
                            enabled=r.enabled, id=r.id)
            for r in conn.execute(sa.text(
                "select id, slug, rules, severity, sort_order, enabled from categories")).all()]
    by_slug = {c.slug: c for c in cats}
    compiled = compile_categories(cats)
    rank = {s: i for i, s in enumerate(("info", "low", "medium", "high", "critical"))}

    # Kategoriya standartidan yuqori jiddiylik ulagichdan kelgan (masalan KEV "high") — qayta tasniflashda
    # pasayib ketmasligi uchun `extra.severity_floor` ga yoziladi
    conn.execute(sa.text(
        "update events e set extra = e.extra || jsonb_build_object('severity_floor', e.severity) "
        "from categories c where e.category_id = c.id and not (e.extra ? 'severity_floor') and "
        "array_position(array['info','low','medium','high','critical'], e.severity) > "
        "array_position(array['info','low','medium','high','critical'], c.severity)"
    ))
    # ransomware / leak — o'z kategoriyasida qoladi
    conn.execute(sa.text(
        "update events set extra = extra || jsonb_build_object('fixed_category', category) "
        "where category in ('ransomware', 'leak')"
    ))
    conn.execute(sa.text(
        "update events e set extra = e.extra || jsonb_build_object('fixed_category', e.category) "
        "from sources s where e.source_id = s.id and s.category_id is not null"
    ))
    rows = conn.execute(sa.text(
        "select id, title, summary, extra from events where category in ('news', 'telegram', 'tg_group') "
        "and not category_locked"
    )).all()
    for r in rows:
        c = classify(r.title, r.summary, compiled)
        cat = by_slug[c.slug]
        floor = (r.extra or {}).get("severity_floor")
        sev = floor if floor and rank.get(floor, 0) > rank.get(cat.severity, 0) else cat.severity
        extra = dict(r.extra or {})
        extra["classifier"] = {"score": c.score, "hits": c.hits}
        conn.execute(sa.text(
            "update events set category = :slug, category_id = :cid, severity = :sev, extra = cast(:extra as jsonb) "
            "where id = :id"
        ), dict(slug=c.slug, cid=cat.id, sev=sev, extra=json.dumps(extra, ensure_ascii=False), id=r.id))


def upgrade() -> None:
    conn = op.get_bind()
    for slug, rules in RULES.items():
        conn.execute(sa.text("update categories set rules = cast(:r as jsonb) where slug = :s"),
                     {"r": json.dumps(rules, ensure_ascii=False), "s": slug})
    _classify_legacy(conn)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "update events set category = case channel when 'telegram_channel' then 'telegram' "
        "when 'telegram_group' then 'tg_group' else 'news' end, category_id = null, severity = 'info' "
        "where not (extra ? 'fixed_category') and coalesce(source_id, 0) not in "
        "(select id from sources where category_id is not null)"
    ))
    conn.execute(sa.text("update events set extra = extra - 'classifier' - 'fixed_category'"))
    conn.execute(sa.text("update categories set rules = '{}'::jsonb"))
