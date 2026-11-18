"""Maqolaning o'z rasmi: RSS media yoki sahifadagi og:image / twitter:image → tekshiruv → 16:9.

Qachon qidirilmaydi (rasm hech qachon olinmaydi — illyustratsiya chiziladi):
- `MEDIA_SOURCE_IMAGES=false`;
- yangilik sayti emas (Telegram kanal / guruh, API — trekerlar): u yerdagi rasm sizib chiqqan ma'lumot skrinshoti yoki
  qurbonning sahifasi bo'lishi mumkin;
- kategoriyasi leak, darkweb-sale, credentials, defacement, ransomware — maqoladagi rasm ham ma'lumot namunasi yoki
  buzilgan sayt ko'rinishi bo'lishi mumkin (spetsifikatsiya: sizib chiqqan ma'lumot namunasi post qilinmaydi);
- manba ishonchliligi underground / community; havola .onion, fayl yuklash, Google News yoki t.me.

Tekshiruv: faqat `HttpFetcher` orqali (SSRF himoyasi — har so'rov va redirect'da DNS: ichki manzillarga yo'q; xost
bo'yicha navbat va pauza). Sahifa ≤ 3 MB, rasm ≤ 8 MB va ≤ 40 Mpiksel; rasm kamida 480×250, landshaft (eni/bo'yi
1.2 … 2.6), shaffof logotip emas, "tekis" (bir rangli fon) emas. SVG va saytlar avtomatik yasaydigan "matnli
ijtimoiy karta" (logotip + sarlavha, masalan habr.com/share/...) yo'q — ular o'rniga illyustratsiya.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from io import BytesIO
from urllib.parse import urljoin, urlsplit

import httpx
from PIL import Image, ImageOps, ImageStat

from app.core.config import settings
from app.services.connectors.base import ConfigError, ConnectorError
from app.services.connectors.http import HttpFetcher

SENSITIVE_CATEGORIES = frozenset({"leak", "darkweb-sale", "credentials", "defacement", "ransomware"})
UNTRUSTED_RELIABILITY = frozenset({"underground", "community"})
BLOCKED_HOSTS = ("news.google.com", "t.me", "telegram.me", "telegram.org", "telegra.ph")
PAGE_MAX = 3 * 1024 * 1024
IMAGE_MAX = 8 * 1024 * 1024
MAX_PIXELS = 40_000_000
MIN_SIZE = (480, 250)
RATIO = (1.2, 2.6)
TIMEOUT = httpx.Timeout(12.0, connect=6.0)
_FILE_EXT = re.compile(r"\.(zip|rar|7z|gz|tgz|tar|sql|csv|txt|json|xlsx?|bak|dump|db|pdf)$", re.IGNORECASE)
_META_KEYS = ("og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src")
_META = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_ATTR = re.compile(r"""([a-zA-Z:_-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""")
_LINK_IMG = re.compile(r"""<link\b[^>]*rel\s*=\s*["']?image_src["']?[^>]*>""", re.IGNORECASE)
# Sayt avtomatik yasagan "ijtimoiy karta" (logotip + sarlavha matni, masalan habr.com/share/...) — foto emas
_TEXT_CARD = re.compile(r"habr\.com/share/|/share/(?:publication|post|article|news)/|/og[-_]?image[s]?/(?:generate|render)"
                        r"|/social[-_]?(?:card|image)s?/|/opengraph-image|/api/og\b", re.IGNORECASE)


class SourceImageError(Exception):
    """Maqola rasmi yo'q yoki yaroqsiz (sababi — matnda; jadvalga yoziladi)."""


def url_hash(url: str) -> str:
    return hashlib.sha1(url.strip().encode()).hexdigest()[:16]


def _host_ok(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not host or host.endswith(".onion"):
        return False
    return not any(host == b or host.endswith("." + b) for b in BLOCKED_HOSTS)


def ineligible(*, category: str | None, channel: str | None, reliability: str | None, url: str | None) -> str | None:
    """Maqola rasmini qidirmaslik sababi (None — qidirish mumkin)."""
    if not settings.media_source_images:
        return "disabled"
    if (channel or "news") != "news":
        return "not_news_site"
    if (category or "") in SENSITIVE_CATEGORIES:
        return "sensitive_category"
    if (reliability or "media") in UNTRUSTED_RELIABILITY:
        return "untrusted_source"
    if not url or not _host_ok(url) or _FILE_EXT.search(urlsplit(url).path or ""):
        return "unsafe_url"
    return None


def page_images(html_text: str, base_url: str) -> list[str]:
    """Sahifa `<head>` idagi og:image / twitter:image / image_src havolalari (tartib — ustuvorlik)."""
    head = html_text[:400_000]
    found: dict[str, str] = {}
    for tag in _META.findall(head):
        attrs = {m.group(1).lower(): (m.group(2) or m.group(3) or m.group(4) or "") for m in _ATTR.finditer(tag)}
        key = (attrs.get("property") or attrs.get("name") or "").strip().lower()
        if key in _META_KEYS and attrs.get("content") and key not in found:
            found[key] = attrs["content"].strip()
    out = [found[k] for k in _META_KEYS if k in found]
    for tag in _LINK_IMG.findall(head):
        attrs = {m.group(1).lower(): (m.group(2) or m.group(3) or m.group(4) or "") for m in _ATTR.finditer(tag)}
        if attrs.get("href"):
            out.append(attrs["href"].strip())
    result: list[str] = []
    for raw in out:
        absolute = urljoin(base_url, raw.replace("&amp;", "&"))
        if (absolute not in result and _host_ok(absolute) and not _TEXT_CARD.search(absolute)
                and not absolute.lower().split("?")[0].endswith(".svg")):
            result.append(absolute)
    return result[:3]


def _check(img: Image.Image) -> None:
    w, h = img.size
    if w * h > MAX_PIXELS:
        raise SourceImageError("too_many_pixels")
    if w < MIN_SIZE[0] or h < MIN_SIZE[1]:
        raise SourceImageError("too_small")
    if not (RATIO[0] <= w / h <= RATIO[1]):
        raise SourceImageError("not_landscape")


def normalize(img: Image.Image) -> Image.Image:
    """Tekshiruvdan o'tgan rasm → RGB 1280×720 (16:9; markazdan, biroz yuqoriroq kesiladi — sarlavha va yuzlar)."""
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        if ImageStat.Stat(rgba.getchannel("A")).mean[0] < 235:
            raise SourceImageError("transparent_logo")
        img = rgba.convert("RGB")
    else:
        img = img.convert("RGB")
    w, h = img.size
    target = 16 / 9
    if w / h > target:
        new_w = int(h * target)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target)
        top = int((h - new_h) * 0.4)
        img = img.crop((0, top, w, top + new_h))
    gray = img.convert("L").resize((64, 36))
    if ImageStat.Stat(gray).stddev[0] < 12:
        raise SourceImageError("flat_image")
    return img.resize((1280, 720), Image.Resampling.LANCZOS)


def decode(data: bytes) -> Image.Image:
    try:
        img = Image.open(BytesIO(data))
        _check(img)
        if img.format == "JPEG":
            img.draft("RGB", (1600, 900))
        img.load()
    except SourceImageError:
        raise
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise SourceImageError(f"bad_image:{type(exc).__name__}") from exc
    if img.format not in ("JPEG", "PNG", "WEBP", "GIF", "AVIF"):
        raise SourceImageError(f"format:{img.format}")
    if getattr(img, "is_animated", False):
        img.seek(0)
    return img


async def fetch_image(http: HttpFetcher, url: str) -> Image.Image:
    try:
        resp = await http.get(url, headers={"Accept": "image/avif,image/webp,image/jpeg,image/png,image/*;q=0.8"},
                              timeout=TIMEOUT)
    except (ConnectorError, ConfigError) as exc:
        raise SourceImageError(f"image_fetch:{str(exc)[:120]}") from exc
    ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype and not ctype.startswith("image/"):
        raise SourceImageError(f"not_image:{ctype[:40]}")
    if "svg" in ctype:
        raise SourceImageError("svg")
    if len(resp.content) > IMAGE_MAX:
        raise SourceImageError("image_too_large")
    img = await asyncio.to_thread(decode, resp.content)
    return await asyncio.to_thread(normalize, img)


async def candidates(http: HttpFetcher, url: str, hinted: str | None) -> list[str]:
    """RSS'dagi rasm (bo'lsa) va maqola sahifasidagi og:image."""
    out: list[str] = []
    if hinted and _host_ok(hinted) and not _TEXT_CARD.search(hinted):
        out.append(hinted)
    try:
        resp = await http.get(url, headers={"Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"},
                              timeout=TIMEOUT, expect_html=True)
    except (ConnectorError, ConfigError) as exc:
        if out:
            return out
        raise SourceImageError(f"page_fetch:{str(exc)[:120]}") from exc
    if "html" not in resp.headers.get("content-type", "html").lower() or len(resp.content) > PAGE_MAX:
        return out
    for cand in page_images(resp.text, str(resp.url)):
        if cand not in out:
            out.append(cand)
    return out


async def find(http: HttpFetcher, url: str, hinted: str | None = None) -> tuple[Image.Image, str]:
    """Birinchi yaroqli rasm va uning URL'i; topilmasa `SourceImageError` (oxirgi sabab bilan)."""
    cands = await candidates(http, url, hinted)
    if not cands:
        raise SourceImageError("no_image_on_page")
    last: SourceImageError | None = None
    for cand in cands[:3]:
        try:
            return await fetch_image(http, cand), cand
        except SourceImageError as exc:
            last = exc
    raise last or SourceImageError("no_usable_image")
