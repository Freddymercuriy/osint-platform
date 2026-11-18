"""Post matni: bitta hodisa → Telegram HTML (tezkor xabar / lenta posti) — kanal tilida.

Qoidalar (spetsifikatsiya, Bosqich 3):
- Hech bir gapni til modeli yozmaydi: sarlavha va matn — hodisaning o'zi yoki saqlangan tarjimasi, qolgani —
  `core/i18n.py` katalogidagi shablonlar (`pub_*`).
- Matn tozalanadi: URL, @mention, hashtag, "obuna bo'ling" qatorlari, emoji, HTML qoldiqlari; shaxsiy ma'lumot
  (email, telefon) olib tashlanadi; .onion va fayl yuklash havolalariga tugma qo'yilmaydi.
- O'zbek kirill: `uz_to_cyrillic` faqat matn maydonlariga, tayyor HTML'ga emas (teglar, hashtag, CVE buzilmasin).
- Hamma matn HTML-escape qilinadi; Telegram faqat &lt; &gt; &amp; &quot; ni taniydi.
- Tezkor xabar ~900 belgidan oshmaydi (telefonda bitta ekran): avval tavsiya, keyin matn gaplari tushiriladi.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.i18n import UZ_CYRL, t
from app.services.i18n.templates import COUNTRY
from app.services.i18n.text import normalize_uz, uz_to_cyrillic

ALERT_MAX = 900  # ko'rinadigan belgilar (telefonda bitta ekran)
TEXT_LIMIT = 4096  # sendMessage chegarasi (entity'lar ajratilgandan keyin)
SUMMARY_SENTENCES = 2
SUMMARY_CHARS = 420

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


@dataclass
class Rendered:
    text: str
    buttons: list[list[dict]]


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


def render_event(v: EventView, lang: str, *, public_app_url: str = "") -> Rendered:
    """Bitta hodisa posti. Matn maydonlari tarjima tilida keladi: avval tozalanadi, keyin kanal yozuviga o'giriladi
    (kirillga o'girilgan URL / email filtrlardan o'tib ketmasin)."""
    def loc(s: str) -> str:  # asl (tarjimasiz) matnning yozuvi o'girilmaydi — inglizcha kirillga aylanmasin
        return localize(s, lang) if v.translated else s
    # sarlavha qatori: band · davlat · kategoriya
    band = v.band if v.band in DOTS else "low"
    head = [f"{DOTS[band]} {esc(band_label(band, lang))}"]
    regional = [c for c in v.countries if c.upper() in FLAGS]
    if regional:
        head.append(" ".join(f"{FLAGS[c.upper()]} {esc(country_name(c, lang))}" for c in regional[:2]))
    elif v.scope == "global" or not v.countries:
        head.append(f"{GLOBE} {esc(t('pub_global', lang))}")
    if v.category_name:
        head.append(esc(localize(v.category_name, lang)))
    header = " · ".join(head)

    title = scrub(v.title) or first_sentences(scrub(v.summary), 1, 120) or "—"
    body = first_sentences(scrub(v.summary))
    if body and (body.lower().startswith(title.lower()[:60]) or title.lower().startswith(body.lower()[:60])):
        body = ""  # matn sarlavhani takrorlasa — ko'rsatilmaydi
    title, body = loc(title), loc(body)

    names = list({outlet(x).lower(): outlet(x) for x in (v.source, *v.also_sources) if x}.values())
    shown = ", ".join(names[:3]) + ("…" if len(names) > 3 else "")
    sources = (t("pub_sources_n", lang, n=len(names), names=shown) if len(names) > 1
               else t("pub_sources_1", lang, names=shown))
    conf = f"<b>{esc(t('pub_conf_label', lang))}:</b> {esc(t(confidence_code(v), lang))} · {esc(sources)}"
    when = f"<i>{esc(fmt_when(v.when, lang))} ({esc(t('pub_tz', lang))})</i>"
    action = (f"<b>{esc(t('pub_action', lang))}:</b> {esc(localize(scrub(v.action), lang))}"
              if v.action and band in ("high", "critical") else "")
    note = f"<i>{esc(t('pub_translation_missing', lang))}</i>" if not v.translated else ""
    tags = [hashtag(c) for c in (regional or ["global"])] + [hashtag(v.category_slug), hashtag(v.sector)]
    tag_line = " ".join(dict.fromkeys(x for x in tags if x))

    def assemble(body_text: str, with_action: bool) -> str:
        parts = [header, f"<b>{esc(title)}</b>", when]
        if body_text:
            parts.append("")
            parts.append(esc(body_text))
        parts.append("")
        parts.append(conf)
        if with_action and action:
            parts.append(action)
        if note:
            parts.append(note)
        if tag_line:
            parts.append("")
            parts.append(tag_line)
        return "\n".join(parts)

    text = assemble(body, True)
    if visible_len(text) > ALERT_MAX:
        text = assemble(body, False)
    if visible_len(text) > ALERT_MAX and body:
        text = assemble(loc(first_sentences(scrub(v.summary), 1, 260)), False)
    if visible_len(text) > ALERT_MAX:
        text = assemble("", False)
    if len(text) > TEXT_LIMIT:  # juda uzun sarlavha (bo'lmasligi kerak) — sarlavhani qisqartirish
        title = title[:300].rsplit(" ", 1)[0] + "…"
        text = assemble("", False)

    buttons: list[list[dict]] = []
    row = []
    url = safe_url(v.url)
    if url:
        row.append({"text": t("pub_btn_source", lang), "url": url})
    if public_app_url:
        row.append({"text": t("pub_btn_platform", lang),
                    "url": f"{public_app_url.rstrip('/')}/dashboard/events?q={v.id}"})
    if row:
        buttons.append(row)
    return Rendered(text=text, buttons=buttons)


def render_test(lang: str, now: datetime) -> str:
    return (f"✅ <b>{esc(t('pub_test_title', lang))}</b>\n"
            f"{esc(t('pub_test_body', lang, when=fmt_when(now, lang), tz=t('pub_tz', lang)))}")
