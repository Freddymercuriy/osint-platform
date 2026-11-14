"""Server-renderli HTML yangiliklar ro'yxati (RSS yo'q saytlar uchun).

config:
  url         — ro'yxat sahifasi (majburiy)
  item        — har bir yozuv uchun CSS selektor (majburiy)
  title       — yozuv ichidagi sarlavha selektori (majburiy)
  link        — yozuv ichidagi havola selektori (majburiy; href sahifa URL'iga nisbatan to'ldiriladi;
                "." — yozuvning o'zi <a> bo'lsa)
  date        — sana selektori (ixtiyoriy)
  date_format — strptime formati yoki "auto" (ixtiyoriy; default "auto")
  summary     — qisqa matn selektori (ixtiyoriy)

Faqat sahifa bilan bir saytdagi (host yoki uning subdomeni) http(s) havolalar olinadi.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup

from app.services.connectors.base import (
    ConfigError,
    Connector,
    FetchContext,
    FetchResult,
    RawItem,
    SourceView,
    register,
)

MAX_ITEMS = 100

# Oy nomlari (ru: bosh va qaratqich kelishik, en, uz lotin, kk/ru qisqa) → oy raqami
_MONTHS: dict[str, int] = {}
for _n, _names in enumerate([
    ("январь", "января", "january", "jan", "yanvar", "қаңтар", "янв"),
    ("февраль", "февраля", "february", "feb", "fevral", "ақпан", "фев"),
    ("март", "марта", "march", "mar", "mart", "наурыз"),
    ("апрель", "апреля", "april", "apr", "aprel", "сәуір", "апр"),
    ("май", "мая", "may", "mayo", "мамыр"),
    ("июнь", "июня", "june", "jun", "iyun", "маусым", "июн"),
    ("июль", "июля", "july", "jul", "iyul", "шілде", "июл"),
    ("август", "августа", "august", "aug", "avgust", "тамыз", "авг"),
    ("сентябрь", "сентября", "september", "sep", "sept", "sentabr", "sentyabr", "қыркүйек", "сен"),
    ("октябрь", "октября", "october", "oct", "oktabr", "oktyabr", "қазан", "окт"),
    ("ноябрь", "ноября", "november", "nov", "noyabr", "қараша", "ноя"),
    ("декабрь", "декабря", "december", "dec", "dekabr", "желтоқсан", "дек"),
], start=1):
    for _name in _names:
        _MONTHS[_name] = _n

_RE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?")
_RE_DMY = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?:\D+(\d{1,2}):(\d{2}))?")
_RE_TEXT = re.compile(r"(\d{1,2})\s+([^\W\d_]+)\.?,?\s+(\d{4})")


def _utc(y: int, mo: int, d: int, h: int = 0, mi: int = 0, s: int = 0) -> datetime | None:
    try:
        return datetime(y, mo, d, h, mi, s, tzinfo=UTC)
    except ValueError:
        return None


def parse_date(text: str, fmt: str | None = "auto") -> datetime | None:
    """Sanani UTC (tz-aware) datetime'ga aylantiradi; tanib bo'lmasa None."""
    text = " ".join((text or "").split())
    if not text:
        return None
    if fmt and fmt != "auto":
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            return None
        return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    if m := _RE_ISO.search(text):
        y, mo, d, h, mi, s = (int(g) if g else 0 for g in m.groups())
        return _utc(y, mo, d, h, mi, s)
    if m := _RE_DMY.search(text):
        d, mo, y, h, mi = (int(g) if g else 0 for g in m.groups())
        return _utc(y, mo, d, h, mi)
    if m := _RE_TEXT.search(text):
        mo = _MONTHS.get(m.group(2).lower())
        if mo:
            return _utc(int(m.group(3)), mo, int(m.group(1)))
    return None


def _site(host: str) -> str:
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host


def same_site(url: str, base: str) -> bool:
    a, b = urlsplit(url), urlsplit(base)
    if a.scheme not in ("http", "https") or not a.hostname:
        return False
    ha, hb = _site(a.hostname), _site(b.hostname or "")
    return ha == hb or ha.endswith("." + hb)


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def _select_one(parent, selector: str):
    if selector.strip() in (".", "self", ":scope"):
        return parent
    return parent.select_one(selector)


def parse_list(html: bytes | str, page_url: str, cfg: dict) -> list[RawItem]:
    soup = BeautifulSoup(html, "html.parser")
    fmt = cfg.get("date_format") or "auto"
    items: list[RawItem] = []
    seen: set[str] = set()
    for node in soup.select(cfg["item"])[:MAX_ITEMS]:
        t_node, l_node = _select_one(node, cfg["title"]), _select_one(node, cfg["link"])
        if t_node is None or l_node is None:
            continue
        href = (l_node.get("href") or "").strip()
        title = _text(t_node)
        if not href or not title:
            continue
        url = urldefrag(urljoin(page_url, href))[0]
        if not same_site(url, page_url) or url in seen:
            continue
        seen.add(url)
        published = None
        if cfg.get("date"):
            d_node = _select_one(node, cfg["date"])
            if d_node is not None:
                published = parse_date(d_node.get("datetime") or _text(d_node), fmt) or parse_date(_text(d_node), fmt)
        summary = _text(_select_one(node, cfg["summary"])) if cfg.get("summary") else ""
        items.append(RawItem(title=title[:300], url=url, summary=summary[:600], published=published))
    return items


@register
class HtmlListConnector(Connector):
    kind = "html_list"
    title = "HTML yangiliklar ro'yxati"
    config_fields = ("url", "item", "title", "link", "date", "date_format", "summary")

    def validate_config(self, config: dict) -> None:
        config = config or {}
        if not str(config.get("url") or "").startswith(("http://", "https://")):
            raise ConfigError("config.url — http(s) manzil bo'lishi kerak")
        for key in ("item", "title", "link"):
            if not str(config.get(key) or "").strip():
                raise ConfigError(f"config.{key} — CSS selektor majburiy")
        for key in ("item", "title", "link", "date", "summary"):
            sel = config.get(key)
            if sel and not isinstance(sel, str):
                raise ConfigError(f"config.{key} — satr bo'lishi kerak")
        probe = BeautifulSoup("<html></html>", "html.parser")
        for key in ("item", "title", "link", "date", "summary"):
            sel = config.get(key)
            if sel and sel.strip() not in (".", "self", ":scope"):
                try:
                    probe.select(sel)
                except Exception as exc:  # noto'g'ri CSS selektor
                    raise ConfigError(f"config.{key} — noto'g'ri CSS selektor") from exc

    def target_urls(self, source: SourceView) -> list[str]:
        return [source.config.get("url", "")]

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        cfg = ctx.source.config
        self.validate_config(cfg)
        resp = await ctx.http.get(cfg["url"], expect_html=True)
        # Redirect'dan keyin yakuniy URL — nisbiy havollar uchun asos
        page_url = str(resp.url) if getattr(resp, "url", None) else cfg["url"]
        items = await asyncio.to_thread(parse_list, resp.content, page_url, cfg)
        return FetchResult(items, resp.status_code)
