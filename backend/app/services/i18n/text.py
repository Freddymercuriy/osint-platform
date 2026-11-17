"""Til aniqlash (evristik, API'siz), o'zbek kirill ↔ lotin transliteratsiyasi va o'zbek matnini normallashtirish."""

from __future__ import annotations

import re

from app.services.i18n.vendor import uztranslit as _uzt

LANGS = ("en", "ru", "uz")  # har hodisa saqlanadigan tillar

_APOS = re.compile("[‘’ʻʼ`´]")
# UZCERT kabi manbalardagi turkcha harflar → o'zbek lotin
_TR_UZ = str.maketrans({"ş": "sh", "Ş": "Sh", "ç": "ch", "Ç": "Ch", "ğ": "g'", "Ğ": "G'", "ö": "o'", "Ö": "O'",
                        "ı": "i"})

_UZ_CYR = set("ўқғҳЎҚҒҲ")
_KK = set("әөүұіңһӘӨҮҰІҢҺ")
_TG = set("ҷӣӯҶӢӮ")
_KY_ONLY = set("ңөүҢӨҮ")
_UZ_LATIN_WORDS = re.compile(
    r"(?<!\w)(?:va|uchun|bilan|bo'yicha|haqida|ham|emas|bo'lgan|qilish|qilindi|aniqlandi|tizim\w*|ma'lumot\w*|"
    r"zaiflik\w*|xavfsizlik\w*|o'zbekiston\w*|toshkent\w*|kerak|orqali|yangi|mumkin|etildi|olindi|bo'ldi)(?!\w)",
    re.IGNORECASE,
)


def normalize_apostrophes(text: str) -> str:
    return _APOS.sub("'", text or "")


def normalize_uz(text: str) -> str:
    """O'zbek lotin matni: apostroflar bir xil (') va turkcha harflar (ş, ç, ö, ğ) o'zbekcha yozuvga."""
    return normalize_apostrophes(text).translate(_TR_UZ)


def detect_lang(text: str, fallback: str = "en") -> str:
    """'en' | 'ru' | 'uz' | 'kk' | 'ky' | 'tg'. O'zbek kirill ham 'uz' (yozuvi `is_cyrillic` bilan aniqlanadi)."""
    sample = (text or "")[:2000]
    cyr = sum(1 for ch in sample if "Ѐ" <= ch <= "ӿ")
    lat = sum(1 for ch in sample if ch.isascii() and ch.isalpha()) + sum(1 for ch in sample if ch in "şçöğıŞÇÖĞ")
    if cyr + lat < 12:
        return fallback
    if cyr > lat:
        chars = set(sample)
        if chars & _TG:  # ҷ, ӣ, ӯ — faqat tojikchada (ҳ, қ, ғ o'zbekcha bilan umumiy)
            return "tg"
        if chars & _UZ_CYR and not chars & (_KK - _KY_ONLY):
            return "uz"
        if chars & (_KK - _KY_ONLY):  # ә, ұ, і, һ — faqat qozoqchada
            return "kk"
        if chars & _KY_ONLY:
            return "ky"
        return "ru"
    words = len(re.findall(r"\w+", sample)) or 1
    uz_hits = len(_UZ_LATIN_WORDS.findall(normalize_uz(sample)))
    if any(ch in sample for ch in "şçöğ") or uz_hits / words >= 0.06 or uz_hits >= 3:
        return "uz"
    return "en"


def is_cyrillic(text: str) -> bool:
    sample = (text or "")[:500]
    cyr = sum(1 for ch in sample if "Ѐ" <= ch <= "ӿ")
    return cyr > sum(1 for ch in sample if ch.isascii() and ch.isalpha())


# ---------------------------------------------------------------- latin.jaybi.uz dvigateli (vendor/uztranslit.py)
_ASCII_APOS = {"okina": "'", "tutuq": "'"}  # platforma qoidasi: lotinda oddiy ' (normalize_apostrophes bilan bir xil)


# Kirillga o'girilmaydigan qismlar (lotinda qoladi): URL / e-mail / @username (dvigatelning o'z qoidasi), {placeholder},
# <code>…</code> va `kod`, teglar, hamda texnik so'zlar — `_keep_latin`.
_PROTECT_RE = re.compile(
    "(?P<skip>" + _uzt._SKIP_RE.pattern + ")"
    r"|(?P<ph>\{[^{}]*\})"
    r"|(?P<code><code>.*?</code>|`[^`]*`)"
    r"|(?P<tag></?[A-Za-z][\w-]*\s*/?>)"
    r"|(?P<tok>[._/@#]?[A-Za-z0-9]+(?:[._/@:#+]+[A-Za-z0-9]+)*)",
    re.S,
)
_CONNECTORS = set("._/@:#+")
_APOS_CHARS = set(_uzt.APOS)
# Lotinda qoladigan nomlar va inglizcha texnik so'zlar (katta-kichik harf farqsiz). Qisqartmalar (API, OSINT) va
# CamelCase (GitHub, RansomLook) avtomatik qoladi — ro'yxatga kerak emas.
KEEP_LATIN = frozenset(w.lower() for w in (
    "Google", "News", "Chrome", "Firefox", "Safari", "Linux", "Windows", "Android", "Docker", "Gravatar", "Cloudflare",
    "Reddit", "Excel", "Word", "BotFather", "uzcard", "humo", "captcha", "certificate", "transparency",
    # inglizcha texnik atamalar (o'zbek kirill matnlarida ham odatda lotinda yoziladi)
    "username", "email", "backend", "frontend", "config", "slug", "bookmark", "ransomware", "leak", "data", "scam",
    "threat", "intel", "public", "sources", "English",
))
# O'zbekcha qisqartmalar — bosh harfli bo'lsa ham kirillga o'giriladi (IIV → ИИВ, AQSh → АҚШ)
UZ_ABBREVIATIONS = frozenset(w.lower() for w in (
    "IIV", "IIB", "IIO", "BMT", "MDH", "AQSh", "DXX", "FVV", "OAV", "YHXB", "MChJ", "OTM", "DTM", "TATU", "SSV",
    "QR", "XK", "AJ", "DUK", "QK", "JK", "MJtK",
))
# O'zbek lotin yozuvida yo'q harflar: c (faqat "ch" tarkibida bor) va w — bunday so'z chet el nomi (Cybercab, Twitter)
_FOREIGN_RE = re.compile(r"c(?!h)|w", re.IGNORECASE)


def _keep_latin(tok: str, text: str, start: int, end: int) -> bool:
    parts = tok.split("/")
    if len(parts) > 1 and all(p.isalpha() for p in parts):  # "ko'rsatish/yashirish" — yo'l emas, so'zlar: har biri alohida
        keep, pos = False, start
        for p in parts:
            keep = _keep_latin(p, text, pos, pos + len(p)) or keep
            pos += len(p) + 1
        return keep
    if any(c in _CONNECTORS for c in tok):  # domen, fayl yo'li, ENV_NOMI, gov.uz (lekin "h.k." — qisqartma)
        return not all(len(part) == 1 and part.islower() for part in re.split(r"[._/@:#+]+", tok.strip("._/@#")))
    if any(c.isdigit() for c in tok) and any(c.isalpha() for c in tok):  # 5G, x86, CVE2026
        return True
    after = text[end + 1:end + 2] if end < len(text) and text[end] in _APOS_CHARS else ""
    if (start and text[start - 1] in _APOS_CHARS) or after.isupper():
        return False  # O'ZBEKISTON, MA'LUMOT — o'zbekcha so'zning bo'lagi (ID'si, backend'ni — yo'q)
    if tok.lower() in UZ_ABBREVIATIONS:
        return False
    if _FOREIGN_RE.search(tok):
        return True
    uppers = sum(c.isupper() for c in tok)
    if uppers >= 2 and (not tok.isupper() or len(tok) <= 6):  # API, OSINT, UZCERT, RansomLook (RESPUBLIKASI — yo'q)
        return True
    return tok.lower() in KEEP_LATIN


def uz_to_cyrillic(text: str) -> str:
    """O'zbek lotin (1995 yoki 2026 alifbosi) → kirill, latin.jaybi.uz qoidalari bilan: ye/e, ts → ц, yo'l → йўл,
    o'zlashma so'zlar lug'ati (obyekt → объект, iyul → июль), bosh harflar. Lotinda qoladi: URL, e-mail, @username,
    {placeholder}, `kod`, teglar, qisqartmalar va texnik so'zlar (API, OSINT, gov.uz, ENV_NOMI, 5G, Google).
    Matn allaqachon kirillda bo'lsa — o'zgarishsiz."""
    text = text or ""
    out: list[str] = []
    last = 0
    for m in _PROTECT_RE.finditer(text):
        if m.lastgroup == "tok" and not _keep_latin(m.group(), text, m.start(), m.end()):
            continue  # oddiy so'z — atrofidagi matn bilan birga o'giriladi
        out.append(_uzt.convert(text[last:m.start()], "auto", "cyr"))
        out.append(m.group())
        last = m.end()
    out.append(_uzt.convert(text[last:], "auto", "cyr"))
    return "".join(out)


def uz_to_latin(text: str) -> str:
    """O'zbek kirill → lotin (1995), latin.jaybi.uz qoidalari bilan (е/э, ц, ъ/ь, сентябрь → sentabr, Исҳоқ → Is'hoq,
    ШАҲАР → SHAHAR ...); barcha apostroflar oddiy ' (platforma qoidasi). Lotin harflari o'zgarmaydi."""
    return normalize_apostrophes(_uzt.convert(text or "", "cyr", "lat", _ASCII_APOS))
