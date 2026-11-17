"""NewsNow mavzu sahifasi (newsnow.com / newsnow.co.uk): sarlavha, nashr nomi, vaqt, NewsNow havolasi.

config: {"url": "https://www.newsnow.com/us/Tech/Cyber+Security/Cyber+Attacks"}

robots.txt (`User-agent: *`) chegarasida ishlaydi: faqat mavzu sahifasining o'zi (birinchi sahifa) o'qiladi —
`?p=` sahifalash, `/A/...` (maqolaga o'tish), `/cgi`, `/share` va boshqa yopiq yo'llarga so'rov yuborilmaydi.
Maqola havolasi (`c.newsnow.com/A/<id>?...`) faqat saqlanadi: uni foydalanuvchi brauzerda ochadi, platforma
o'zi unga kirmaydi. Asl maqola matni olinmaydi (sahifada faqat sarlavha bor).

Sahifa tuzilishi (2026-11): `article.article-card` → `a.article-card__headline[href]` (`.article-title` — sarlavha),
`.article-publisher__name`, `.article-publisher__timestamp[data-timestamp]` (unix vaqt). Bitta maqola sahifada
bir necha bo'limda (top / latest / popular) takrorlanadi — `/A/<id>` bo'yicha bitta qilinadi. Havoladagi `?...`
qo'shimchasi ochilishlar orasida o'zgarishi mumkin, shuning uchun takror kaliti — maqola ID'si (`newsnow:<id>`).
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from app.services.connectors.base import (
    ConfigError,
    Connector,
    ConnectorError,
    FetchContext,
    FetchResult,
    RawItem,
    SourceBlocked,
    SourceView,
    register,
)
from app.services.connectors.http import looks_like_challenge

NEWSNOW_TAG = "(NewsNow)"
HOSTS = frozenset({"www.newsnow.com", "newsnow.com", "www.newsnow.co.uk", "newsnow.co.uk"})
# robots.txt (User-agent: *) dagi yopiq yo'llar — mavzu sahifasi URL'i ular bilan boshlanmasligi kerak
_DISALLOWED = ("/subscribe", "/cgi-bin", "/livefeed", "/a/", "/share", "/cgi/", "/brand-new-look.html", "/reg/",
               "/housead", "/http:", "/https:", "/ico/", "/pharos.js", "/test-please-ignore/")
_ARTICLE = re.compile(r"^https://c\.newsnow\.(?:com|co\.uk)/A/(\d+)(?:[?#]|$)")
_ANY_ARTICLE = re.compile(r"newsnow\.(?:com|co\.uk)/a/\d")  # tashxis uchun (kichik harfdagi matnda)
MAX_ITEMS = 100


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node is not None else ""


def _timestamp(node) -> datetime | None:
    raw = (node.get("data-timestamp") or "").strip() if node is not None else ""
    if not raw.isdigit():
        return None
    try:
        return datetime.fromtimestamp(int(raw), UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _item(link, box, page_url: str, seen: set[str]) -> RawItem | None:
    """`link` — maqola havolasi, `box` — nashr / vaqt qidiriladigan konteyner (kartochka yoki ota element)."""
    url = urljoin(page_url, (link.get("href") or "").strip())
    m = _ARTICLE.match(url)
    title = _text(link.select_one(".article-title") or link)
    if not m or not title or m.group(1) in seen:
        return None
    seen.add(m.group(1))
    outlet = _text(box.select_one(".article-publisher__name, .src")) if box is not None else ""
    ts = box.select_one("[data-timestamp], [data-time]") if box is not None else None
    if ts is not None and not ts.get("data-timestamp"):
        ts = {"data-timestamp": ts.get("data-time")}
    flag = box.select_one(".article-card__flag [data-tooltip]") if box is not None else None
    extra = {"newsnow_id": m.group(1)}
    if flag is not None and flag.get("data-tooltip"):
        extra["publisher_country"] = flag["data-tooltip"][:64]  # nashr davlati (voqea davlati emas)
    return RawItem(
        title=title[:300], url=url, published=_timestamp(ts),
        source_name=f"{outlet} {NEWSNOW_TAG}"[:128] if outlet else None,
        dedup_key=f"newsnow:{m.group(1)}", extra=extra,
    )


def _box(link, levels: int = 4):
    """Zaxira: havoladan yuqoriga — nashr nomi yoki vaqti bor eng yaqin ota element (boshqa maqolasiz)."""
    node = link.parent
    for _ in range(levels):
        if node is None or node.name in ("body", "html"):
            return None
        if node.select_one(".article-publisher__name, .src, [data-timestamp], [data-time]") is not None:
            return node if len(node.select("a[href*='/A/']")) <= 2 else None
        node = node.parent
    return None


def parse_page(html: bytes | str, page_url: str) -> list[RawItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[RawItem] = []
    seen: set[str] = set()
    for card in soup.select("article.article-card"):
        link = card.select_one("a.article-card__headline[href]")
        if link is not None and (it := _item(link, card, page_url, seen)) is not None:
            items.append(it)
        if len(items) >= MAX_ITEMS:
            return items
    if not items:
        # Kartochka belgilari boshqacha (masalan server boshqa shablon bergan) — maqola havolalari bo'yicha
        for link in soup.select("a[href*='/A/']"):
            if (it := _item(link, _box(link), page_url, seen)) is not None:
                items.append(it)
            if len(items) >= MAX_ITEMS:
                break
    return items


def fingerprint(html: bytes | str) -> str:
    """Yangilik topilmaganda admin uchun qisqa tashxis (sahifa matni emas, faqat belgilar soni)."""
    text = html.decode("utf-8", "replace") if isinstance(html, bytes) else html
    low = text.lower()
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    title = " ".join(m.group(1).split())[:80] if m else "—"
    js = any(k in low for k in ("enable javascript", "javascript is required", "javascript required"))
    links = len(_ANY_ARTICLE.findall(low))
    return (f"{len(text) // 1024} KB, <title>: {title!r}, <article>: {low.count('<article')}, "
            f"article-card: {low.count('article-card')}, /A/ havola: {links}, <script>: {low.count('<script')}"
            + (", 'JavaScript kerak' matni bor" if js else ""))


def check_url(url: str) -> None:
    parts = urlsplit(str(url or "").strip())
    if parts.scheme != "https" or (parts.hostname or "").lower() not in HOSTS:
        raise ConfigError("config.url — https://www.newsnow.com/... yoki https://www.newsnow.co.uk/... mavzu sahifasi")
    path = parts.path.lower()
    if path in ("", "/") or path.startswith(_DISALLOWED):
        raise ConfigError("config.url — mavzu sahifasi bo'lishi kerak (robots.txt yopiq yo'llari taqiqlangan)")
    if parts.query:
        raise ConfigError("config.url — so'rov qatorisiz (?p= sahifalash robots.txt'da yopiq)")


@register
class NewsNowConnector(Connector):
    kind = "newsnow"
    title = "NewsNow mavzu sahifasi"
    config_fields = ("url",)

    def validate_config(self, config: dict) -> None:
        check_url((config or {}).get("url"))

    def target_urls(self, source: SourceView) -> list[str]:
        return [source.config.get("url", "")]

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        url = str(ctx.source.config.get("url") or "").strip()
        check_url(url)
        resp = await ctx.http.get(url, expect_html=True)
        final = urlsplit(str(resp.url)) if getattr(resp, "url", None) else None
        if final is not None and ((final.hostname or "").lower() not in HOSTS or final.query):
            raise ConnectorError(f"NewsNow boshqa sahifaga yo'naltirdi: {str(resp.url)[:120]}",
                                 http_status=resp.status_code)
        items = await asyncio.to_thread(parse_page, resp.content, url)
        if not items:
            if looks_like_challenge(resp):
                raise SourceBlocked("Manba blokladi: challenge/CAPTCHA sahifasi", http_status=resp.status_code)
            # Yangiliksiz mavzu sahifasi bo'lmaydi — tuzilma o'zgargan (jim "ok" bo'lib qolmasin)
            raise ConnectorError(
                "NewsNow: sahifada yangilik topilmadi (sahifa tuzilishi o'zgargan yoki sayt botlarga boshqa sahifa "
                f"bergan) — {fingerprint(resp.content)}", http_status=resp.status_code)
        return FetchResult(items, resp.status_code)
