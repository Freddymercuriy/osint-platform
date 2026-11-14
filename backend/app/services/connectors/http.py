"""HTTP qatlami: xostlar bo'yicha navbat va pauza, shartli so'rovlar, holat kodlarini xatolarga aylantirish,
SSRF himoyasi.

- Bir xostga bir vaqtda bitta so'rov; ketma-ket so'rovlar orasida tasodifiy 1–4 s pauza.
- `If-None-Match` / `If-Modified-Since` — manba ETag / Last-Modified bergan bo'lsa; 304 → "o'zgarmagan".
- 401 → AuthMissing; 403 / challenge sahifasi → SourceBlocked; 429 / 503+Retry-After → RateLimited.
- Har so'rovdan oldin (redirect'lar ham) xost DNS orqali tekshiriladi: xususiy, loopback, link-local va
  boshqa ichki manzillarga so'rov yuborilmaydi (admin kiritgan URL server ichkarisiga yo'l bo'lmasligi uchun).

User-Agent ochiq aytadi: bu platformaning o'quvchisi (brauzerga o'xshatilmaydi).
"""

from __future__ import annotations

import asyncio
import ipaddress
import random
import socket
import time
from email.utils import parsedate_to_datetime
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from app.services.connectors.base import (
    AuthMissing,
    ConfigError,
    ConnectorError,
    RateLimited,
    SourceBlocked,
)

USER_AGENT = "Mozilla/5.0 (compatible; OSINT-Platform/2.0; +https://github.com/Freddymercuriy/osint-platform)"
TIMEOUT = httpx.Timeout(20.0, connect=10.0)
MAX_BYTES = 25 * 1024 * 1024

# Bir xostga ketma-ket so'rovlar orasidagi pauza (s). Testlar 0 qiladi.
PAUSE_RANGE: tuple[float, float] = (1.0, 4.0)

_CHALLENGE_MARKERS = (
    "cf-browser-verification", "challenge-platform", "cf_chl_", "just a moment...", "attention required!",
    "g-recaptcha", "h-captcha", "hcaptcha.com", "captcha-delivery", "ddos-guard", "please enable javascript and cookies",
)


# ---------------------------------------------------------------- SSRF
class BlockedAddress(ConfigError):
    pass


def _resolve(host: str) -> list[str]:
    return list({ai[4][0] for ai in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)})


# Testlar almashtiradi (tarmoqsiz)
RESOLVER = _resolve

# Muvaffaqiyatli DNS javoblari qisqa muddat keshlanadi (har so'rovda qayta resolve qilinmasin)
DNS_TTL = 300.0
_dns_cache: dict[str, tuple[list[str], float]] = {}


def _is_public(ip: str) -> bool:
    addr = ipaddress.ip_address(ip.split("%", 1)[0])
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return not (
        addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast
        or addr.is_reserved or addr.is_unspecified or not addr.is_global
    )


async def assert_public_url(url: str) -> None:
    """URL sxemasi http(s) va xost faqat ommaviy manzillarga resolve bo'lishi kerak."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise BlockedAddress(f"Faqat http(s) URL ruxsat etilgan: {url[:120]}")
    host = parts.hostname
    cached = _dns_cache.get(host)
    if cached and cached[1] > time.monotonic():
        ips = cached[0]
    else:
        try:
            ips = [host] if _is_ip(host) else await asyncio.to_thread(RESOLVER, host)
        except OSError as exc:
            raise ConnectorError(f"DNS: {host} topilmadi ({exc})") from exc
        if ips:
            _dns_cache[host] = (ips, time.monotonic() + DNS_TTL)
    if not ips:
        raise ConnectorError(f"DNS: {host} topilmadi")
    bad = [ip for ip in ips if not _is_public(ip)]
    if bad:
        raise BlockedAddress(f"Ichki/xususiy manzil taqiqlangan: {host} → {', '.join(sorted(bad))}")


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------- xostlar navbati
class _HostGate:
    __slots__ = ("lock", "ready_at")

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.ready_at = 0.0


_gates: dict[str, _HostGate] = {}


def _gate(host: str) -> _HostGate:
    gate = _gates.get(host)
    if gate is None:
        gate = _gates[host] = _HostGate()
    return gate


def reset_gates() -> None:
    _gates.clear()
    _dns_cache.clear()


# ---------------------------------------------------------------- yordamchilar
def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def looks_like_challenge(resp: httpx.Response) -> bool:
    if resp.headers.get("cf-mitigated", "").lower() == "challenge":
        return True
    ctype = resp.headers.get("content-type", "")
    if "html" not in ctype:
        return False
    head = resp.text[:6000].lower()
    return any(m in head for m in _CHALLENGE_MARKERS)


def raise_for_status(resp: httpx.Response, expect_html: bool = False) -> None:
    """Holat kodi / challenge sahifasini manba xatosiga aylantiradi."""
    code = resp.status_code
    if code == 401:
        raise AuthMissing("Kalit rad etildi yoki talab qilinadi (HTTP 401)", http_status=code)
    if code == 429 or (code == 503 and resp.headers.get("retry-after")):
        raise RateLimited(f"So'rovlar cheklandi (HTTP {code})", http_status=code,
                          retry_after=parse_retry_after(resp.headers.get("retry-after")))
    if code == 403 or (code in (503, 520, 521, 522, 523) and looks_like_challenge(resp)):
        why = "challenge/CAPTCHA sahifasi" if looks_like_challenge(resp) else "kirish taqiqlandi"
        raise SourceBlocked(f"Manba blokladi: {why} (HTTP {code})", http_status=code)
    if code >= 400:
        raise ConnectorError(f"HTTP {code}", http_status=code)
    if not expect_html and code == 200 and looks_like_challenge(resp):
        raise SourceBlocked("Manba blokladi: challenge/CAPTCHA sahifasi qaytdi", http_status=code)


class HttpFetcher:
    """Ulagichlar ishlatadigan HTTP mijoz (bitta jarayonda bitta `httpx.AsyncClient`)."""

    def __init__(self, client: httpx.AsyncClient, ssrf_guard: bool = True) -> None:
        self.client = client
        self.ssrf_guard = ssrf_guard
        self.requests = 0
        self.last_status: int | None = None

    @classmethod
    def create(cls, transport: httpx.AsyncBaseTransport | None = None, ssrf_guard: bool = True) -> HttpFetcher:
        holder: dict[str, HttpFetcher] = {}

        async def _check(request: httpx.Request) -> None:
            if holder["self"].ssrf_guard:
                await assert_public_url(str(request.url))

        client = httpx.AsyncClient(
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
            follow_redirects=True,
            max_redirects=5,
            transport=transport,
            event_hooks={"request": [_check]},
        )
        fetcher = cls(client, ssrf_guard=ssrf_guard)
        holder["self"] = fetcher
        return fetcher

    async def aclose(self) -> None:
        await self.client.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        expect_html: bool = False,
        allow_not_modified: bool = False,
        raise_errors: bool = True,
        **kwargs,
    ) -> httpx.Response:
        host = urlsplit(url).hostname or ""
        headers = dict(kwargs.pop("headers", None) or {})
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        gate = _gate(host)
        async with gate.lock:
            wait = gate.ready_at - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                resp = await self.client.request(method, url, headers=headers, **kwargs)
            except httpx.TimeoutException as exc:
                raise ConnectorError(f"Vaqt tugadi: {host}") from exc
            except ConfigError:
                raise
            except httpx.HTTPError as exc:
                raise ConnectorError(f"Ulanish xatosi: {host}: {type(exc).__name__}") from exc
            finally:
                lo, hi = PAUSE_RANGE
                gate.ready_at = time.monotonic() + (random.uniform(lo, hi) if hi > 0 else 0)
        self.requests += 1
        self.last_status = resp.status_code
        length = resp.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BYTES:
            raise ConnectorError(f"Javob juda katta ({int(length) // 1024 // 1024} MB)", http_status=resp.status_code)
        if resp.status_code == 304 and allow_not_modified:
            return resp
        if raise_errors:
            raise_for_status(resp, expect_html=expect_html)
        return resp

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("POST", url, **kwargs)
