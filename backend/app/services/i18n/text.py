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


# ---------------------------------------------------------------- o'zbek kirill → lotin (rasmiy jadval)
_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l",
    "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ч": "ch",
    "ш": "sh", "щ": "sh", "ъ": "'", "ь": "", "ы": "i", "э": "e", "ю": "yu", "я": "ya", "ё": "yo", "ў": "o'",
    "қ": "q", "ғ": "g'", "ҳ": "h", "ц": "s",
}
_VOWELS = set("аеёиоуэюяўАЕЁИОУЭЮЯЎ")


def translit_uz(text: str) -> str:
    """O'zbek kirill → lotin. "е" so'z boshida va unlidan keyin "ye"; "ц" unlidan keyin "ts"."""
    out: list[str] = []
    prev = ""
    for ch in text or "":
        low = ch.lower()
        if low == "е":
            lat = "ye" if (not prev or not prev.isalpha() or prev in _VOWELS) else "e"
        elif low == "ц":
            lat = "ts" if prev in _VOWELS else "s"
        elif low in _MAP:
            lat = _MAP[low]
        else:
            out.append(ch)
            prev = ch
            continue
        if ch.isupper() and lat:
            lat = lat[0].upper() + lat[1:]
        out.append(lat)
        prev = ch
    return normalize_apostrophes("".join(out))


# ---------------------------------------------------------------- latin.jaybi.uz dvigateli (vendor/uztranslit.py)
_ASCII_APOS = {"okina": "'", "tutuq": "'"}  # platforma qoidasi: lotinda oddiy ' (normalize_apostrophes bilan bir xil)


def uz_to_cyrillic(text: str) -> str:
    """O'zbek lotin (1995 yoki 2026 alifbosi) → kirill, latin.jaybi.uz qoidalari bilan: ye/e, ts → ц, yo'l → йўл,
    o'zlashma so'zlar lug'ati (obyekt → объект, iyul → июль), bosh harflar; URL, e-mail va @username o'zgarmaydi.
    Matn allaqachon kirillda bo'lsa — o'zgarishsiz."""
    return _uzt.convert(text or "", "auto", "cyr")


def uz_to_latin(text: str) -> str:
    """O'zbek kirill → lotin (1995), latin.jaybi.uz qoidalari bilan (е/э, ц, ъ/ь, сентябрь → sentabr ...);
    apostroflar oddiy '. Lotin harflari o'zgarmaydi."""
    return _uzt.convert(text or "", "cyr", "lat", _ASCII_APOS)
