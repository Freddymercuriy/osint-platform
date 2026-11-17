"""Takror yangiliklar: bitta voqeani turli nashrlar turlicha sarlavha (va tilda) bosadi.

Sarlavha "imzo"ga aylantiriladi:
  - muhim so'zlar tushunchaga keltiriladi (til va sinonimdan qat'i nazar):
    "хакеры" / "hackers" / "взломали" → #HACK, "Таджикистана" / "Tajik" → #TJ,
    "украли" / "похитили" / "steal" → #STEAL ...
  - qolgan so'zlar — birinchi 5 harfi (qo'pol stemming); bog'lovchi so'zlar tashlanadi.

Ikki sarlavha bitta voqea deb hisoblanadi, agar:
  - barcha tokenlar bo'yicha Jaccard ≥ 0.5 (bir tildagi o'xshash sarlavhalar), YOKI
  - kamida 4 ta umumiy tushuncha va tushunchalar bo'yicha Jaccard ≥ 0.5
    (turli tildagi / boshqacha yozilgan sarlavhalar).
Veto (turli voqea): ikkalasida ham davlat ko'rsatilgan, lekin umumiy davlat yo'q
("... Узбекистана" / "... Казахстана"); yoki ikkalasida ham soha ko'rsatilgan, lekin
umumiysi yo'q ("... банка" / "... клиники").

Cheklov: bir davlatda 3 kun ichida deyarli bir xil yozilgan ikki XIL voqea (soha so'zisiz)
bittaga birlashishi mumkin; butunlay boshqa so'zlar bilan yozilgan bir voqea alohida qoladi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TOKEN_THRESHOLD = 0.5  # barcha tokenlar bo'yicha Jaccard
CONCEPT_THRESHOLD = 0.5  # faqat tushunchalar bo'yicha Jaccard
CONCEPT_MIN_SHARED = 4  # ... va kamida shuncha umumiy tushuncha

# tushuncha → so'z boshlanishlari (kichik harf, apostrofsiz, "ё" → "е")
_COUNTRIES: dict[str, tuple[str, ...]] = {
    "UZ": ("uzbek", "ozbek", "узбек", "ўзбек", "tashkent", "toshkent", "ташкент", "тошкент"),
    "KZ": ("kazakh", "kazak", "kazah", "qozoq", "qozog", "казах", "қазақ", "қозоқ", "қозоғ",
           "astana", "астан", "almaty", "алматы"),
    "KG": ("kyrgyz", "kirgiz", "kirghiz", "qirgiz", "киргиз", "кыргыз", "қирғиз", "қырғыз",
           "bishkek", "бишкек"),
    "TJ": ("tajik", "tadjik", "tojik", "таджик", "тоҷик", "тожик", "dushanbe", "душанбе"),
    "TM": ("turkmen", "turkman", "туркмен", "ashgabat", "ashkhabad", "ашхабад", "ашгабат"),
}

_SECTORS: dict[str, tuple[str, ...]] = {
    "GOV": ("госорган", "государствен", "правительств", "министер", "ведомств", "government",
            "govt", "ministr", "vazirlik", "hukumat", "мемлекеттік"),
    "BANK": ("банк", "нацбанк", "bank"),
    "HEALTH": ("больниц", "клиник", "медицин", "поликлиник", "hospital", "clinic", "health",
               "medical", "shifoxona", "tibbiy"),
    "TELECOM": ("телеком", "провайдер", "telecom", "provayder"),
    "EDU": ("университет", "школ", "universit", "school", "maktab"),
    # Muhim infratuzilma (rahbariyat kanali ustuvorligi): energetika va transport
    "ENERGY": ("энергет", "энергосист", "электроэнерг", "электростанц", "электросет", "нефтегаз", "нефтян",
               "energy", "electricity", "energetika", "elektroenerg", "elektrostans", "neftgaz", "энергия"),
    "TRANSPORT": ("транспорт", "аэропорт", "авиакомпан", "железнодорож", "авиаперевоз", "airport", "airline",
                  "railroad", "transport", "aeroport", "aviakompan", "temiryo"),
}

_TOPICS: dict[str, tuple[str, ...]] = {
    "HACK": ("хакер", "ҳакер", "хакнул", "хакнут", "взлом", "взлам", "hack", "xaker"),
    "ATTACK": ("атак", "кибератак", "attack", "cyberattack", "hujum", "шабуыл"),
    "STEAL": ("украл", "украд", "украст", "похит", "похищ", "краж", "хищен", "steal", "stole",
              "theft", "ogirla", "ўғирла", "ұрла"),
    "LEAK": ("утечк", "утек", "слив", "слит", "leak", "breach", "exposed", "sizib", "sizdi",
             "сизиб", "сизди"),
    "DATA": ("данн", "data", "records", "malumot", "маълумот", "деректер"),
    "DOC": ("документ", "файл", "document", "files", "hujjat", "ҳужжат"),
    "AI": ("искусствен", "интеллект", "нейросет", "artificial", "suniy"),
    "SPY": ("шпион", "слеж", "spy", "spied", "spying", "espionage", "josus"),
    "MAIL": ("почт", "email", "mail", "pochta"),
    "RANSOM": ("ransom", "вымогат", "шифровальщ"),
    "PHISH": ("phish", "фишинг", "fishing"),
    "FRAUD": ("мошенн", "афер", "fraud", "scam", "firibgar", "алаяқ"),
    "VULN": ("уязвим", "vulnerab", "zaiflik"),
    "MALWARE": ("malware", "spyware", "вредонос", "зловред", "троян", "вирус", "trojan", "virus"),
    "SEC": ("безопасн", "нацбезопасн", "кибербезопасн", "security", "cybersecurity", "defence",
            "defense", "xavfsizlik", "қауіпсіздік"),
}

# Qisqa (4 harfdan kam) lekin muhim so'zlar — aynan mos kelganda
_EXACT: dict[str, str] = {"ии": "#AI", "ai": "#AI", "spy": "#SPY", "фсб": "фсб", "fsb": "фсб"}

_STOP = frozenset("""
with from that this than more over into have been were then made used uses using after about
their they what when will says said amid behind linked links suspected related could would
после более были было была быть может могли могут который которые которых чтобы через этого
этом свои своих также почему почти заявил заявили сообщил сообщили сообщило помощью стало
bilan uchun orqali mumkin haqida boyicha ham esa
""".split())

_PREFIXES: list[tuple[str, str]] = sorted(
    ((p, f"#{name}") for group in (_COUNTRIES, _SECTORS, _TOPICS)
     for name, prefixes in group.items() for p in prefixes),
    key=lambda x: -len(x[0]),  # uzunroq boshlanish ustun: "spyware" → #MALWARE, "spy" → #SPY
)
_COUNTRY_TAGS = frozenset(f"#{c}" for c in _COUNTRIES)
_SECTOR_TAGS = frozenset(f"#{s}" for s in _SECTORS)

_APOSTROPHES = re.compile("['‘’ʻʼ`]")
_THOUSANDS = re.compile(r"(?<=\d)[,.  ](?=\d{3}(?!\d))")  # "2,000" → "2000"


@dataclass(frozen=True)
class TitleSig:
    tokens: frozenset[str]  # tushunchalar ("#HACK") + boshqa so'zlarning o'zaklari
    concepts: frozenset[str]
    countries: frozenset[str]
    sectors: frozenset[str]


def _token(word: str) -> str | None:
    if word in _EXACT:
        return _EXACT[word]
    if word.isdigit():
        return word if len(word) >= 3 else None
    if len(word) < 4 or word in _STOP:
        return None
    for prefix, tag in _PREFIXES:
        if word.startswith(prefix):
            return tag
    return word[:5]


def signature(title: str) -> TitleSig:
    text = _APOSTROPHES.sub("", (title or "").lower().replace("ё", "е"))
    text = _THOUSANDS.sub("", text)
    tokens = frozenset(t for w in re.findall(r"\w+", text) if (t := _token(w)))
    concepts = frozenset(t for t in tokens if t.startswith("#"))
    return TitleSig(tokens, concepts, concepts & _COUNTRY_TAGS, concepts & _SECTOR_TAGS)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def same_story(a: TitleSig, b: TitleSig) -> bool:
    if a.countries and b.countries and not (a.countries & b.countries):
        return False
    if a.sectors and b.sectors and not (a.sectors & b.sectors):
        return False
    if len(a.tokens) >= 3 and len(b.tokens) >= 3 and _jaccard(a.tokens, b.tokens) >= TOKEN_THRESHOLD:
        return True
    return (
        len(a.concepts & b.concepts) >= CONCEPT_MIN_SHARED
        and _jaccard(a.concepts, b.concepts) >= CONCEPT_THRESHOLD
    )
