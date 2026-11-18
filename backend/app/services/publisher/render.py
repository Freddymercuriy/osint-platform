"""Post matni: bitta hodisa → Telegram HTML (tezkor xabar / lenta posti) — kanal tilida.

Qoidalar (spetsifikatsiya, Bosqich 3):
- Hech bir gapni til modeli yozmaydi: sarlavha va matn — hodisaning o'zi yoki saqlangan tarjimasi, qolgani —
  `core/i18n.py` katalogidagi shablonlar (`pub_*`).
- Matn tozalanadi: URL, @mention, hashtag, "obuna bo'ling" qatorlari, emoji, HTML qoldiqlari; shaxsiy ma'lumot
  (email, telefon) olib tashlanadi; .onion va fayl yuklash havolalariga tugma qo'yilmaydi.
- O'zbek kirill: `uz_to_cyrillic` faqat matn maydonlariga, tayyor HTML'ga emas (teglar, hashtag, CVE buzilmasin).
- Hamma matn HTML-escape qilinadi; Telegram faqat &lt; &gt; &amp; &quot; ni taniydi.
- Post tuzilishi: rubrika | hudud, daraja (o'rta va yuqori), sarlavha, vaqt, 1–2 gap, 📌 asosiy ma'lumotlar (faqat
  manbada bor maydonlar: CVE aynan, CVSS matnda yozilgan bo'lsa, guruh, soha, yozuvlar), ⚠️ nima uchun muhim
  (ustuvorlik sabablari), ✅ tavsiya (kategoriya shabloni), 🔎 manba va ishonchlilik, hashtaglar.
- Rasm izohi 1024 belgi (UTF-16): ~1000 dan oshsa avval "nima uchun muhim", keyin ikkinchi gap tushiriladi,
  ma'lumotlar 3 qatorga qisqaradi; tavsiya va ma'lumotlar sig'masa — rasmli postga javob xabarida (`more`).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.i18n import MESSAGES as _CATALOGUE, UZ_CYRL, t
from app.services.i18n.templates import COUNTRY, _num
from app.services.i18n.text import normalize_uz, uz_to_cyrillic

ALERT_MAX = 900  # ko'rinadigan belgilar (telefonda bitta ekran)
TEXT_LIMIT = 4096  # sendMessage chegarasi (entity'lar ajratilgandan keyin)
SUMMARY_SENTENCES = 2
SUMMARY_CHARS = 420

_CATALOGUE_KEYS = frozenset(_CATALOGUE)
DOTS = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}
FLAGS = {"UZ": "🇺🇿", "KZ": "🇰🇿", "KG": "🇰🇬", "TJ": "🇹🇯", "TM": "🇹🇲"}
GLOBE = "🌐"

# --------------------------------------------------------------------------- tozalash
_HTML_TAG = re.compile(r"<[^>]{1,200}>")
_URL = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]{8,}\.onion\b\S*", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_MENTION = re.compile(r"(?<![\w@])@[A-Za-z]\w{3,}")
_HASHTAG = re.compile(r"(?<![\w#])#\w+")
# telefon: xalqaro (+998 90 123 45 67) va mahalliy (90 123-45-67) — yozuvlar soni kabi raqamlarni tegmaslik uchun tor
_PHONE_INTL = re.compile(r"(?<![\w+])\+\d[\d\s().-]{7,}\d(?!\d)")
_PHONE_LOCAL = re.compile(r"(?<!\d)\(?\d{2,3}\)?[\s-]\d{3}[\s-]\d{2}[\s-]\d{2}(?!\d)")
# emoji va bezak belgilari (strelkalar, chiziqlar, ■ ● ★ ...); qochish ketma-ketliklari — ko'rinmas belgilar manbada bo'lmasin
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2B00-\u2BFF\u2190-\u21FF"
                    "\u2500-\u25FF\uFE0F\u200D\u20E3]+")
_PROMO_LINE = re.compile(r"(подпис|obuna|kanalimiz|subscribe|join us|присоединяй|реклама|reklama|канал:|bizni kuzat)",
                         re.IGNORECASE)
_SPACES = re.compile("[ \t\u00A0]+")
_SENTENCE = re.compile(r"(?<=[.!?…])\s+(?=[\"«(]?[A-ZА-ЯЁЎҚҒҲ0-9])")
_FILE_EXT = re.compile(r"\.(zip|rar|7z|gz|tgz|tar|sql|csv|txt|json|xlsx?|bak|dump|db)$", re.IGNORECASE)


def scrub(text: str | None) -> str:
    """HTML, URL, email, telefon, @mention, hashtag, emoji va reklama qatorlarisiz bitta qatorli matn."""
    text = html.unescape(_HTML_TAG.sub(" ", text or ""))
    lines = [ln for ln in text.splitlines() if not _PROMO_LINE.search(ln)]
    text = " ".join(lines)
    for rx in (_URL, _EMAIL, _PHONE_INTL, _PHONE_LOCAL, _MENTION, _HASHTAG, _EMOJI):
        text = rx.sub(" ", text)
    text = _SPACES.sub(" ", text).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", text).strip(" -–—|·:")


def first_sentences(text: str, n: int = SUMMARY_SENTENCES, limit: int = SUMMARY_CHARS) -> str:
    """Birinchi `n` gap, `limit` belgigacha; gap chegarasi bo'lmasa — so'z chegarasida "…"."""
    if not text:
        return ""
    out = ""
    for sentence in _SENTENCE.split(text)[:n]:
        candidate = f"{out} {sentence}".strip()
        if len(candidate) > limit:
            break
        out = candidate
    if not out:
        cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-–— ")
        out = cut + ("…" if len(text) > len(cut) else "")
    return out


def safe_url(url: str | None) -> str | None:
    """Tugma uchun havola: faqat http(s), .onion emas, sizib chiqqan fayl yuklash emas."""
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not host or host.endswith(".onion"):
        return None
    if _FILE_EXT.search(parts.path or ""):
        return None
    return url.strip()


def esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def visible_len(html_text: str) -> int:
    return len(html.unescape(_HTML_TAG.sub("", html_text)))


def plain(html_text: str) -> str:
    """HTML → oddiy matn (parse xatosida qayta yuborish uchun)."""
    return html.unescape(_HTML_TAG.sub("", html_text))


# --------------------------------------------------------------------------- til yordamchilari
def base_lang(lang: str) -> str:
    """Kanal tili → tarjima tili (`event_translations.lang`): uz-Cyrl uz dan hosil qilinadi."""
    return "uz" if lang == UZ_CYRL else lang


def localize(text: str, lang: str) -> str:
    """Hodisa matni (o'zbek lotin) → kanal yozuvi."""
    if lang == UZ_CYRL:
        return uz_to_cyrillic(text)
    if lang == "uz":
        return normalize_uz(text)
    return text


def country_name(code: str, lang: str) -> str:
    names = COUNTRY.get(code.upper())
    if not names:
        return code.upper()
    return localize(names["uz"], lang) if lang in ("uz", UZ_CYRL) else names.get(lang, names["en"])


def fmt_when(dt: datetime, lang: str) -> str:
    """18-noyabr, 14:05 · 18 ноября, 14:05 · 18 November, 14:05 (Toshkent vaqti)."""
    local = dt.astimezone(ZoneInfo(settings.app_timezone))
    month = t("pub_months", lang).split(",")[local.month - 1]
    hm = local.strftime("%H:%M")
    if lang in ("uz", UZ_CYRL):
        return f"{local.day}-{month}, {hm}"
    return f"{local.day} {month}, {hm}"


def band_label(band: str, lang: str) -> str:
    """KRITIK / КРИТИК ...: katta harfli so'zni transliteratsiya qisqartma deb o'girmaydi — kichik harfda o'giriladi."""
    if lang == UZ_CYRL:
        return uz_to_cyrillic(t(f"pub_band_{band}", "uz").lower()).upper()
    return t(f"pub_band_{band}", lang)


_VIA = re.compile(r"\s*\([^)]*\)\s*$")


def outlet(name: str) -> str:
    """"CyberScoop (NewsNow)" → "CyberScoop": agregator orqali kelgan bir nashr ikki manba hisoblanmasin."""
    return _VIA.sub("", name or "").strip() or (name or "").strip()


def hashtag(value: str | None) -> str | None:
    tag = re.sub(r"[^A-Za-z0-9_]", "_", (value or "").strip()).strip("_")
    return f"#{tag}" if tag and not tag[0].isdigit() else None


# --------------------------------------------------------------------------- post
RUBRIC_ICONS = {"cyber": "🛡", "vulnerability": "🔐", "ai": "🤖", "tech": "💻", "telecom": "📡", "economy": "💰",
                "politics": "🏛"}
GEO_CA, GEO_WORLD = "🌏", "🌍"
CAPTION_LIMIT = 1024  # sendPhoto izohi — Telegram UTF-16 birliklarida sanaydi
POST_BUDGET = 1000  # rasm izohi va matnli post uchun bir xil (zaxira bilan)
FACT_ACTOR_CATEGORIES = frozenset({"ransomware", "espionage", "malware", "leak", "darkweb-sale", "defacement",
                                   "credentials", "phishing", "research"})
_CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
_CVSS = re.compile(r"\bCVSS(?:\s*v?\d(?:\.\d)?)?\D{0,20}?(?<![vV\d.,])(10(?:[.,]0)?|\d[.,]\d)(?!\d)", re.IGNORECASE)


def cves_in(*texts: str | None) -> list[str]:
    """CVE identifikatorlari — matndagi tartibda, aynan (faqat katta harfga keltiriladi)."""
    out: list[str] = []
    for text in texts:
        for m in _CVE.finditer(text or ""):
            cve = m.group(0).upper()
            if cve not in out:
                out.append(cve)
    return out


def cvss_in(*texts: str | None) -> str | None:
    """Matnda aniq yozilgan CVSS bahosi ("CVSS 9.8", "CVSS v3.1 score of 9.8"); taxmin qilinmaydi."""
    for text in texts:
        m = _CVSS.search(text or "")
        if m:
            return m.group(1).replace(",", ".")
    return None


def tg_len(html_text: str) -> int:
    """Telegram sanaydigan uzunlik: teglarsiz matn, UTF-16 birliklarida (emoji — 2)."""
    return len(plain(html_text).encode("utf-16-le")) // 2


@dataclass
class EventView:
    """Postga kerakli hamma narsa (rejalashtiruvchi bazadan yig'adi) — render sof funksiya bo'lsin."""

    id: int
    title: str  # tarjima tilidagi sarlavha (uz-Cyrl kanal uchun — o'zbek lotin; yozuvni render o'giradi) yoki asl
    summary: str
    url: str | None
    when: datetime
    band: str
    countries: list[str]
    scope: str
    category_slug: str
    category_name: str  # tarjima tilida (uz-Cyrl uchun — lotin)
    sector: str | None
    source: str
    reliability: str
    also_sources: list[str] = field(default_factory=list)
    action: str = ""  # kategoriya tavsiyasi (tarjima tilida)
    translated: bool = True  # false — asl matn (tarjima tayyor emas)
    rubric: str = "cyber"  # media.rubric — sarlavha bo'limi
    cves: list[str] = field(default_factory=list)  # asl matndan, aynan
    cvss: str | None = None
    actor: str | None = None
    records: int | None = None
    reasons: list[dict] = field(default_factory=list)  # priority_reasons → "Nima uchun muhim?"


@dataclass
class Rendered:
    text: str  # rasm izohi (yoki matnli post)
    buttons: list[list[dict]]
    more: str = ""  # izohga sig'magan bo'limlar — rasmli postga javob (followup); bo'sh — yo'q


def confidence_code(v: EventView) -> str:
    if v.reliability == "official":
        return "pub_conf_official"
    if len({outlet(x).lower() for x in (v.source, *v.also_sources)}) >= 2:
        return "pub_conf_multi"
    if v.reliability == "tracker":
        return "pub_conf_group_claim" if v.category_slug == "ransomware" else "pub_conf_tracker"
    if v.reliability == "underground":
        return "pub_conf_underground"
    if v.reliability == "community":
        return "pub_conf_community"
    return "pub_conf_media"


def caps(code: str, lang: str, **params) -> str:
    """Katalog matni katta harfda. Kirillda: avval kichik harfda o'giriladi (katta harfli so'zni transliterator
    qisqartma deb lotinda qoldirmasin), keyin katta harf."""
    if lang == UZ_CYRL:
        return uz_to_cyrillic(t(code, "uz", **params).lower()).upper()
    return t(code, lang, **params).upper()


def _sector_name(sector: str | None, lang: str) -> str | None:
    if not sector or f"pub_sector_{sector}" not in _CATALOGUE_KEYS:
        return None
    return t(f"pub_sector_{sector}", lang)


def why_text(v: EventView, lang: str) -> str:
    """"Nima uchun muhim?" — faqat ustuvorlik sabablaridan (kuzatuv ro'yxati, davlat + soha, yozuvlar, eskilik);
    ishonchlilik qatori aytadiganlari (rasmiy, bir nechta manba, yashirin kanal) va sarlavhadagi davlat takrorlanmaydi."""
    parts: list[str] = []
    by_code: dict[str, dict] = {}
    for r in v.reasons or []:
        if isinstance(r, dict) and r.get("code"):
            by_code.setdefault(str(r["code"]), r)
            if r["code"] in ("watch_org", "watch_product", "watch_person") and r.get("arg"):
                parts.append(t(f"pub_why_{r['code']}", lang, name=str(r["arg"])))
    country = "UZ" if "country_uz" in by_code else str((by_code.get("country_ca") or {}).get("arg") or "") or None
    sector = _sector_name((by_code.get("sector") or {}).get("arg"), lang)
    if sector:
        sector_text = sector if lang == "ru" else sector.lower()
        if country and f"pub_in_{country}" in _CATALOGUE_KEYS:
            parts.append(t("pub_why_country_sector", lang, place=t(f"pub_in_{country}", lang), sector=sector_text))
        else:
            parts.append(t("pub_why_sector", lang, sector=sector_text))
    for code in ("records_1m", "records_100k"):
        if code in by_code and by_code[code].get("arg"):
            parts.append(t("pub_why_records", lang, count=_num(by_code[code]["arg"], "uz" if lang == UZ_CYRL else lang)))
            break
    if "stale" in by_code and by_code["stale"].get("arg"):
        parts.append(t("pub_why_stale", lang, hours=by_code["stale"]["arg"]))
    if not parts:
        return ""
    text = "; ".join(parts)
    return text[0].upper() + text[1:] + ("" if text.endswith(".") else ".")


def render_event(v: EventView, lang: str, *, public_app_url: str = "", photo: bool = False) -> Rendered:
    """Bitta hodisa posti (rasm izohi yoki matn). Matn maydonlari tarjima tilida keladi: avval tozalanadi, keyin
    kanal yozuviga o'giriladi (kirillga o'girilgan URL / email filtrlardan o'tib ketmasin). `photo` — izoh bo'ladi
    (1024 belgi); sig'magan bo'limlar `more` ga (rasmli postga javob)."""
    def loc(s: str) -> str:  # asl (tarjimasiz) matnning yozuvi o'girilmaydi — inglizcha kirillga aylanmasin
        return localize(s, lang) if v.translated else s

    band = v.band if v.band in DOTS else "low"
    rubric = v.rubric if v.rubric in RUBRIC_ICONS else "cyber"
    regional = [c.upper() for c in v.countries if c.upper() in FLAGS]
    if regional:
        geo = " ".join(f"{FLAGS[c]} {esc(country_name(c, lang).upper())}" for c in regional[:2])
    elif v.scope != "global":
        geo = f"{GEO_CA} {esc(caps('pub_geo_ca', lang))}"
    else:
        geo = f"{GEO_WORLD} {esc(caps('pub_geo_world', lang))}"
    header = f"{RUBRIC_ICONS[rubric]} <b>{esc(caps(f'pub_rubric_{rubric}', lang))}</b> | <b>{geo}</b>"
    level = f"{DOTS[band]} <b>{esc(caps(f'pub_level_{band}', lang))}</b>" if band in ("critical", "high", "medium") \
        else ""

    title = scrub(v.title) or first_sentences(scrub(v.summary), 1, 120) or "—"
    summary = scrub(v.summary)
    body2, body1 = first_sentences(summary), first_sentences(summary, 1, 260)
    low_title = title.lower()
    if body2 and (body2.lower().startswith(low_title[:60]) or low_title.startswith(body2.lower()[:60])):
        body2 = body1 = ""  # matn sarlavhani takrorlasa — ko'rsatilmaydi
    title, body2, body1 = loc(title), loc(body2), loc(body1)
    when = f"<i>{esc(fmt_when(v.when, lang))} ({esc(t('pub_tz', lang))})</i>"

    # 📌 asosiy ma'lumotlar — faqat manbada bor maydonlar
    facts: list[str] = []
    if v.cves:
        facts.append(f"• {esc(t('pub_fact_cve', lang))}: {esc(', '.join(v.cves[:3]))}")
    if v.cvss:
        facts.append(f"• {esc(t('pub_fact_cvss', lang))}: {esc(v.cvss)}")
    if v.actor and v.category_slug in FACT_ACTOR_CATEGORIES:
        facts.append(f"• {esc(t('pub_fact_actor', lang))}: {esc(scrub(v.actor)[:60])}")
    sector = _sector_name(v.sector, lang)
    if sector:
        facts.append(f"• {esc(t('pub_fact_sector', lang))}: {esc(sector)}")
    if v.records and v.records >= 1000:
        facts.append(f"• {esc(t('pub_fact_records', lang))}: {esc(_num(v.records, 'uz' if lang == UZ_CYRL else lang))}")
    if len(regional) > 2:
        facts.append(f"• {esc(t('pub_fact_region', lang))}: {esc(', '.join(country_name(c, lang) for c in regional))}")

    def section(icon: str, code: str, lines: list[str]) -> str:
        return "\n".join([f"{icon} <b>{esc(caps(code, lang))}</b>", *lines]) if lines else ""

    important = band in ("critical", "high", "medium")
    why = why_text(v, lang) if important else ""
    action = localize(scrub(v.action), lang) if v.action and important else ""
    sec_facts = section("📌", "pub_sec_facts", facts)
    sec_facts3 = section("📌", "pub_sec_facts", facts[:3])
    sec_why = section("⚠️", "pub_sec_why", [esc(why)] if why else [])
    sec_action = section("✅", "pub_sec_action", [esc(action)] if action else [])

    names = list({outlet(x).lower(): outlet(x) for x in (v.source, *v.also_sources) if x}.values())
    shown = ", ".join(names[:3]) + ("…" if len(names) > 3 else "")
    source_line = (f"🔎 <b>{esc(t('pub_source_label', lang))}:</b> {esc(shown)} · "
                   f"<i>{esc(t(confidence_code(v), lang))}</i>")
    note = f"<i>{esc(t('pub_translation_missing', lang))}</i>" if not v.translated else ""
    tags = [hashtag(c) for c in (regional or ["global"])] + [hashtag(v.category_slug), hashtag(v.sector)]
    tag_line = " ".join(dict.fromkeys(x for x in tags if x))

    def assemble(title_text: str, body: str, blocks: list[str]) -> str:
        parts = [header] + ([level] if level else []) + ["", f"<b>{esc(title_text)}</b>", when]
        if body:
            parts += ["", esc(body)]
        for block in blocks:
            if block:
                parts += ["", block]
        parts += ["", source_line] + ([note] if note else []) + ([tag_line] if tag_line else [])
        return "\n".join(parts)

    plans = [  # (matn, izohdagi bo'limlar, javobga o'tadigan bo'limlar) — birinchi sig'gani
        (body2, [sec_facts, sec_why, sec_action], []),
        (body2, [sec_facts, sec_action], []),
        (body1, [sec_facts, sec_action], []),
        (body1, [sec_facts3, sec_action], []),
        (body1, [sec_facts3], [sec_action]),
        (body1, [], [sec_facts, sec_action]),
        ("", [], [sec_facts, sec_action]),
    ]
    text, more_blocks = "", []
    for body, blocks, moved in plans:
        text = assemble(title, body, blocks)
        more_blocks = [b for b in moved if b]
        if tg_len(text) <= POST_BUDGET:
            break
    if tg_len(text) > POST_BUDGET:  # juda uzun sarlavha — so'z chegarasida qisqartiriladi
        short = title[:240].rsplit(" ", 1)[0] + "…"
        text = assemble(short, "", [])
    more = "\n\n".join(more_blocks)

    buttons: list[list[dict]] = []
    row = []
    url = safe_url(v.url)
    if url:
        row.append({"text": f"🌐 {t('pub_btn_source', lang)}", "url": url})
    if public_app_url:
        row.append({"text": t("pub_btn_platform", lang),
                    "url": f"{public_app_url.rstrip('/')}/dashboard/events?q={v.id}"})
    if row:
        buttons.append(row)
    return Rendered(text=text, buttons=buttons, more=more)


def render_test(lang: str, now: datetime) -> str:
    return (f"✅ <b>{esc(t('pub_test_title', lang))}</b>\n"
            f"{esc(t('pub_test_body', lang, when=fmt_when(now, lang), tz=t('pub_tz', lang)))}")
