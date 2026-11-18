"""Rubrika (yirik mavzu guruhi) va rasm motivi — hodisa kategoriyasi + sarlavha / matndagi kalit so'zlar.

Platforma kategoriyalari (leak, ransomware, vulnerability ...) batafsil va o'zgarmaydi; rubrika — o'quvchi uchun
yirik bo'lim: kanal posti sarlavhasi ("🛡 KIBERXAVFSIZLIK | 🇺🇿 O'ZBEKISTON"), kartadagi yorliq va illyustratsiya
uslubi. Rubrikalar: cyber, vulnerability, ai, tech, telecom, economy, politics.

- Kategoriyasi aniq kiber hodisa (leak, ransomware, phishing ...) — `cyber`; `vulnerability` — `vulnerability`.
- `other`, `advisory`, `ddos-outage` — kalit so'zlar: sarlavhadagi moslik 3 ball, matn boshidagi — 1 ball; eng ko'p
  ball olgan rubrika, teng bo'lsa `ORDER` tartibi. Hech narsa topilmasa: other → cyber (yig'uvchi kiber-filtrdan
  o'tgan), advisory → politics, ddos-outage → telecom.
Natija tasodifiy emas: bir xil matn — doim bir xil rubrika va motiv.
"""

from __future__ import annotations

import re

RUBRICS = ("cyber", "vulnerability", "ai", "tech", "telecom", "economy", "politics")
ORDER = ("vulnerability", "ai", "telecom", "economy", "politics", "cyber", "tech")

CYBER_CATEGORIES = frozenset({
    "leak", "malware", "ransomware", "credentials", "espionage", "phishing", "fraud", "research", "law-enforcement",
    "darkweb-sale", "defacement",
})
DEFAULT_RUBRIC = {"other": "cyber", "advisory": "politics", "ddos-outage": "telecom"}


def _rx(words: str) -> re.Pattern[str]:
    alts = "|".join(w.strip() for w in words.split("|") if w.strip())
    return re.compile(rf"(?<![\w])(?:{alts})", re.IGNORECASE)


_APOS = re.compile("['‘’ʻʼ`]")

KEYWORDS: dict[str, re.Pattern[str]] = {
    "vulnerability": _rx(r"cve-\d{4}-\d+| vulnerab\w*| уязвим\w*| zaiflik\w*| заифлик\w*| zero-day| 0-day| нулевого дня"
                         r"| security update\w*| обновлени\w* безопасност\w*| patch tuesday| rce\b"),
    "ai": _rx(r"ai\b| a\.i\.| ии\b| gpt\w*| chatgpt| llm\w*| openai| anthropic| claude\b| gemini\b| deepseek| copilot"
              r"| нейросет\w*| нейронн\w*| искусственн\w* интеллект\w*| suniy intellekt\w*| сунъий интеллект\w*"
              r"| artificial intelligence| machine learning| машинн\w* обучени\w*| generative| генеративн\w*"
              r"| deepfake\w*| дипфейк\w*"),
    "telecom": _rx(r"telecom\w*| телеком\w*| telekom\w*| провайдер\w*| provayder\w*| мобильн\w* связ\w*| mobil aloqa"
                   r"| 5g\b| 4g\b| lte\b| starlink| satellite\w*| спутник\w*| yoldosh\w*| beeline| ucell| uzmobile"
                   r"| mobiuz| kcell| tele2| роскомнадзор| vpn\w*| outage\w*| сбой связи| сбо\w* интернет\w*"
                   r"| internet uzilish\w*| интернет узилиш\w*| отключени\w* интернет\w*| internet shutdown"
                   r"| операторы? связи| aloqa operator\w*"),
    "economy": _rx(r"bank\w*| банк\w*| tolov\w*| тўлов\w*| платеж\w*| платёж\w*| payment\w*| fintech\w*| финтех\w*"
                   r"| crypto\w*| крипто\w*| kripto\w*| bitcoin| биткоин\w*| economy| economic\w*| эконом\w*"
                   r"| iqtisod\w*| иқтисод\w*| invest\w*| инвест\w*| tax\b| налог\w*| soliq\w*| солиқ\w*| trade\b"
                   r"| торгов\w*| savdo\w*| e-commerce| marketplace\w*| маркетплейс\w*| currency| валют\w*"
                   r"| valyuta\w*| stock market| бирж\w*| fond bozori"),
    "politics": _rx(r"law\b| laws\b| закон\w*| qonun\w*| қонун\w*| legislat\w*| parliament\w*| парламент\w*"
                    r"| parlament\w*| majlis\w*| мажилис\w*| senat\w*| сенат\w*| president\w*| президент\w*"
                    r"| prezident\w*| government\w*| правительств\w*| hukumat\w*| ҳукумат\w*| ministr\w*"
                    r"| министр\w*| министерств\w*| vazirlik\w*| вазирлик\w*| regulat\w*| регулир\w*| regulyator\w*"
                    r"| sanction\w*| санкци\w*| sanksiya\w*| политик\w*| siyosat\w*| сиёсат\w*"
                    r"| diplomat\w*| дипломат\w*| nato\b| нато\b| election\w*| выбор\w*| saylov\w*| decree\w*"
                    r"| указ\w*| farmon\w*| фармон\w*| javobgarlik\w*| жавобгарлик\w*| ответственност\w*| штраф\w*"
                    r"| jarima\w*| жарима\w*| кодекс\w*| kodeks\w*| liability"),
    "cyber": _rx(r"cyber\w*| кибер\w*| kiber\w*| hack\w*| хакер\w*| хак\w*| xaker\w*| взлом\w*| attack\w*| атак\w*"
                 r"| hujum\w*| ҳужум\w*| breach\w*| утечк\w*| слив\w*| leak\w*| sizib| сизиб| malware| вредонос\w*"
                 r"| ransomware| вымогател\w*| phishing| фишинг\w*| fishing| fraud\w*| мошенн\w*| firibgar\w*"
                 r"| фирибгар\w*| scam\w*| ddos| ддос| botnet\w*| ботнет\w*| exploit\w*| эксплойт\w*| security\b"
                 r"| безопасност\w*| xavfsizlik\w*| хавфсизлик\w*| darknet\w*| даркнет\w*| stealer\w*| стилер\w*"
                 r"| spyware| шпион\w*| josus\w*| жосус\w*| apt\d*\b| osint| bug bounty| infosec| cert\b"),
    "tech": _rx(r"technolog\w*| технолог\w*| texnolog\w*| software| программн\w*| dasturiy| cloud\b| облач\w*"
                r"| bulutli| microsoft| google| apple\b| android| ios\b| windows| linux| chip\w*| чип\w*"
                r"| processor\w*| процессор\w*| smartphone\w*| смартфон\w*| smartfon\w*| digital\w*| цифров\w*"
                r"| raqamli| рақамли| startup\w*| стартап\w*| gadget\w*| robot\w*| робот\w*"),
}


def _norm(text: str) -> str:
    return _APOS.sub("", (text or "").lower().replace("ё", "е"))


def _hits(rx: re.Pattern[str], text: str) -> int:
    return len({m.group(0).strip() for m in rx.finditer(text)})


def rubric_of(category: str | None, title: str, summary: str = "") -> str:
    """Hodisaning rubrikasi (`RUBRICS` dan biri)."""
    cat = (category or "other").lower()
    if cat == "vulnerability":
        return "vulnerability"
    if cat in CYBER_CATEGORIES:
        return "cyber"
    head, body = _norm(title), _norm(summary)[:400]
    scores = {r: 3 * _hits(KEYWORDS[r], head) + _hits(KEYWORDS[r], body) for r in ORDER}
    if cat == "ddos-outage" and re.search(r"ddos|ддос|botnet|ботнет", head + " " + body):
        return "cyber"
    best = max(ORDER, key=lambda r: (scores[r], -ORDER.index(r)))
    if scores[best] == 0:
        return DEFAULT_RUBRIC.get(cat, "cyber")
    if cat == "ddos-outage" and best not in ("telecom", "cyber"):
        return "telecom"
    return best


# ------------------------------------------------------------------ rasm motivi (illyustratsiya ikonkasi)
_MOTIF_BY_CATEGORY = {
    "ransomware": "lock", "leak": "database", "darkweb-sale": "database", "credentials": "key", "malware": "bug",
    "phishing": "hook", "fraud": "card", "espionage": "eye", "defacement": "browser", "law-enforcement": "gavel",
    "research": "magnifier", "advisory": "document",
}
_MOTIF_BY_RUBRIC = {
    "cyber": "shield", "vulnerability": "bug", "ai": "neural", "tech": "chip", "telecom": "antenna",
    "economy": "chart", "politics": "building",
}
_MOTIF_HINTS: list[tuple[str, re.Pattern[str]]] = [
    ("hook", _rx(r"phishing| фишинг\w*| fishing")),
    ("lock", _rx(r"ransomware| вымогател\w*| шифровальщ\w*")),
    ("server", _rx(r"ddos| ддос| botnet\w*| ботнет\w*| server\w*| сервер\w*")),
    ("broken_link", _rx(r"outage\w*| сбо\w*| uzilish\w*| отключени\w*| shutdown| ishdan chiq\w*")),
    ("phone", _rx(r"android| iphone| ios\b| smartphone\w*| смартфон\w*| smartfon\w*| mobile app\w*| мобильн\w* прилож\w*")),
    ("envelope", _rx(r"email\w*| e-mail| почт\w*| pochta\w*| outlook| exchange\b")),
    ("globe", _rx(r"global\w*| worldwide| dunyo\w*| мир\w*| international| xalqaro| международн\w*")),
]


def motif_of(category: str | None, rubric: str, title: str, summary: str = "") -> str:
    """Illyustratsiya ikonkasi: aniq kategoriya → o'z ikonkasi; aks holda matndagi ishora yoki rubrika ikonkasi."""
    cat = (category or "other").lower()
    if cat in _MOTIF_BY_CATEGORY:
        return _MOTIF_BY_CATEGORY[cat]
    if cat == "vulnerability":
        head = _norm(title)
        if re.search(r"patch|update|yangilan|обновлен|исправ|tuzat", head):
            return "shield_check"
        return "shield_crack" if re.search(r"exploit|faol|актив|hujum|атак|attack", head) else "bug"
    if cat == "ddos-outage":
        text = _norm(f"{title} {summary}")
        return "server" if re.search(r"ddos|ддос|botnet|ботнет", text) else "broken_link"
    if rubric in ("ai", "economy", "politics", "telecom"):
        return _MOTIF_BY_RUBRIC[rubric]
    text = _norm(title)
    for motif, rx in _MOTIF_HINTS:
        if rx.search(text):
            return motif
    return _MOTIF_BY_RUBRIC.get(rubric, "shield")
