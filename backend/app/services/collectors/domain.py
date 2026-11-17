from __future__ import annotations

import asyncio
import ipaddress
import re
from datetime import datetime, timezone
from typing import Any

import dns.asyncresolver
import dns.exception
import dns.resolver
import dns.reversename
import httpx

from app.core.i18n import CodedValueError, current_lang, t
from app.services.collectors.base import BaseCollector, CollectResult

# Generic User-Agent (shaxsiy ma'lumotsiz)
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# DB cheklovlari
_MAX_SOURCE = 64
_MAX_TYPE = 32
_MAX_VALUE = 512
_MAX_DETAIL = 512
_MAX_URL = 1024

_DOMAIN_RE = re.compile(r"[a-z0-9-]{1,63}(\.[a-z0-9-]{1,63})+")
_HOST_RE = _DOMAIN_RE  # WHOIS server nomi uchun ham xuddi shu qoida

# Har bir manba uchun vaqt cheklovlari (sekund) — butun run ~15 s dan oshmaydi
_DNS_TIMEOUT = 10.0
_WHOIS_TIMEOUT = 13.0
_CRT_TIMEOUT = 12.5
_RDAP_HTTP_TIMEOUT = 7.0


def _cut(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _res(
    source: str,
    type_: str,
    value: str,
    detail: str | None = None,
    status: str = "found",
    confidence: float = 0.9,
    url: str | None = None,
    raw: dict[str, Any] | None = None,
) -> CollectResult:
    """CollectResult ni DB cheklovlariga mos (kesilgan) holda yaratadi."""
    return CollectResult(
        source=_cut(source, _MAX_SOURCE) or "",
        type=_cut(type_, _MAX_TYPE) or "",
        value=_cut(value, _MAX_VALUE) or "",
        url=_cut(url, _MAX_URL),
        detail=_cut(detail, _MAX_DETAIL),
        status=status,
        confidence=confidence if status == "found" else 0.0,
        raw=raw or {},
    )


def _normalize(query: str) -> tuple[str, str]:
    """So'rovni normallashtiradi. ("ip"|"domain", qiymat) qaytaradi yoki ValueError."""
    s = (query or "").strip().lower()
    if not s:
        raise CodedValueError("domain_query_empty")
    if "://" in s:
        s = s.split("://", 1)[1]
    elif s.startswith("//"):
        s = s[2:]
    s = re.split(r"[/?#]", s, maxsplit=1)[0]
    if "@" in s:
        s = s.rsplit("@", 1)[1]
    if not s:
        raise CodedValueError("domain_not_found")

    host = s
    if s.startswith("["):  # [ipv6]:port
        end = s.find("]")
        if end == -1:
            raise CodedValueError("invalid_ipv6")
        host = s[1:end]
    elif s.count(":") >= 2:  # port'siz IPv6
        host = s
    elif ":" in s:
        host, port = s.rsplit(":", 1)
        if not port.isdigit():
            raise CodedValueError("invalid_port")

    host = host.split("%", 1)[0]  # IPv6 zone id
    try:
        return "ip", str(ipaddress.ip_address(host))
    except ValueError:
        pass

    host = host.rstrip(".")
    if not host:
        raise CodedValueError("domain_not_found")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        raise CodedValueError("invalid_idna") from None
    if (
        len(host) > 253
        or not _DOMAIN_RE.fullmatch(host)
        or not re.search(r"[a-z]", host.rsplit(".", 1)[1])
    ):
        raise CodedValueError("invalid_domain")
    return "domain", host


# ----------------------------------------------------------------- DNS yordamchilari


def _resolver() -> dns.asyncresolver.Resolver:
    r = dns.asyncresolver.Resolver()
    r.lifetime = 3.0
    r.timeout = 1.5
    return r


_dns_sem: asyncio.Semaphore | None = None


async def _query(name: str, rdtype: str) -> list[Any]:
    """Yozuvlar ro'yxati; NXDOMAIN / yozuv yo'q bo'lsa []; boshqa xatolar ko'tariladi.

    Resolverni ortiqcha yuklamaslik uchun parallel so'rovlar cheklangan, timeoutda 1 marta qayta uriniladi.
    """
    global _dns_sem
    if _dns_sem is None:
        _dns_sem = asyncio.Semaphore(4)
    for attempt in (0, 1):
        try:
            async with _dns_sem:
                answers = await _resolver().resolve(name, rdtype)
            return list(answers)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return []
        except dns.exception.Timeout:
            if attempt:
                raise
    return []


def _txt_strings(rdata: Any) -> str:
    return b"".join(rdata.strings).decode("utf-8", "replace")


def _t(code: str, **params: Any) -> str:
    """Joriy so'rov tilidagi matn (contextvar)."""
    return t(code, current_lang(), **params)


def _err_text(exc: BaseException) -> str:
    if isinstance(exc, (dns.exception.Timeout, asyncio.TimeoutError, httpx.TimeoutException)):
        return _t("c_dom_timeout")
    if isinstance(exc, (httpx.HTTPError, OSError)):
        return _t("c_dom_unreachable")
    return exc.__class__.__name__


# ----------------------------------------------------------------- sanalar


_DATE_FORMATS = ("%d-%b-%Y", "%d.%m.%Y", "%Y.%m.%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y")


def _norm_date(value: str | None) -> str | None:
    """Turli formatdagi sanani YYYY-MM-DD ga keltiradi."""
    if not value:
        return None
    v = value.strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", v)
    if m:
        return m.group(0)
    token = v.split()[0] if v.split() else ""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(token, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _expiry_result(domain: str, expires: str | None) -> CollectResult | None:
    if not expires:
        return None
    try:
        exp = datetime.strptime(expires, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    days = (exp - datetime.now(timezone.utc)).days
    if days < 0:
        detail = _t("c_dom_expired", days=-days, date=expires)
    elif days < 30:
        detail = _t("c_dom_expiring", days=days, date=expires)
    else:
        detail = _t("c_dom_expires_in", days=days, date=expires)
    return _res(
        _t("c_dom_expiry_src"), "whois", domain, detail, raw={"expires": expires, "days_left": days}
    )


# ----------------------------------------------------------------- WHOIS / RDAP


def _vcard_fn(entity: dict[str, Any]) -> tuple[str | None, str | None]:
    """(kind, fn) — vCard'dan faqat tashkilot/registrator nomi uchun."""
    kind, fn, _ = _vcard_names(entity)
    return kind, fn


def _vcard_names(entity: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """(kind, fn, org). Faqat nomlar o'qiladi — email/tel/adr hech qachon."""
    kind = fn = org = None
    arr = entity.get("vcardArray")
    if isinstance(arr, list) and len(arr) > 1 and isinstance(arr[1], list):
        for item in arr[1]:
            if not isinstance(item, list) or len(item) < 4:
                continue
            if item[0] == "fn":
                fn = str(item[3])
            elif item[0] == "kind":
                kind = str(item[3])
            elif item[0] == "org":
                org = str(item[3]) if not isinstance(item[3], list) else str(item[3][0])
    return kind, fn, org


def _parse_rdap_domain(data: dict[str, Any]) -> dict[str, Any]:
    registrar = None
    for ent in data.get("entities") or []:
        if "registrar" in (ent.get("roles") or []):
            # fn ba'zan jismoniy shaxs ismi (masalan .uz: fn="F.I.Sh.", org="Kompaniya") —
            # shuning uchun avval org; fn faqat vCard uni shaxs deb belgilamagan bo'lsa olinadi.
            kind, fn, org = _vcard_names(ent)
            registrar = org or (fn if (kind or "").lower() != "individual" else None)
            if not registrar:  # ba'zi serverlar nomni publicIds'da beradi
                for pid in ent.get("publicIds") or []:
                    registrar = registrar or pid.get("identifier")
            break
    created = updated = expires = None
    for ev in data.get("events") or []:
        action = ev.get("eventAction")
        date = _norm_date(ev.get("eventDate"))
        if action == "registration":
            created = date
        elif action == "expiration":
            expires = date
        elif action == "last changed":
            updated = date
    ns = sorted(
        {
            str(n.get("ldhName", "")).lower().rstrip(".")
            for n in data.get("nameservers") or []
            if n.get("ldhName") and "not.defined" not in str(n["ldhName"])
        }
    )
    return {
        "registrar": registrar,
        "created": created,
        "updated": updated,
        "expires": expires,
        "status": [str(s) for s in data.get("status") or []],
        "nameservers": ns,
    }


_NOT_FOUND_MARKERS = (
    "not found",
    "no match",
    "no entries found",
    "no data found",
    "not registered",
    "no object found",
    "domain available",
    "status: available",
    "status: free",
)


def _parse_whois_text(text: str) -> dict[str, Any] | None:
    """Klassik WHOIS matnidan faqat xavfsiz maydonlarni oladi.

    Registrant/admin/tech bloklari HECH QACHON o'qilmaydi.
    None -> domen ro'yxatdan o'tmagan.
    """
    low = text.lower()
    out: dict[str, Any] = {
        "registrar": None,
        "created": None,
        "updated": None,
        "expires": None,
        "status": [],
        "nameservers": [],
    }
    ns: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("%", "#", ">>>")) or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if not val:
            continue
        if key in ("registrar", "sponsoring registrar"):
            out["registrar"] = out["registrar"] or val
        elif key in ("creation date", "created", "registered", "registered on", "domain registration date"):
            out["created"] = out["created"] or _norm_date(val)
        elif key in ("updated date", "last updated", "last modified", "changed"):
            out["updated"] = out["updated"] or _norm_date(val)
        elif key in (
            "expiration date",
            "registry expiry date",
            "expiry date",
            "expires",
            "paid-till",
            "registrar registration expiration date",
        ):
            out["expires"] = out["expires"] or _norm_date(val)
        elif key in ("status", "domain status"):
            out["status"].append(val.split()[0] if key == "domain status" else val)
        elif key in ("name server", "nserver", "nameserver"):
            host = val.split()[0].lower().rstrip(".")
            if host and host != "not.defined":
                ns.add(host)
    out["nameservers"] = sorted(ns)
    has_data = out["registrar"] or out["created"] or out["expires"] or ns
    if not has_data:
        if any(m in low for m in _NOT_FOUND_MARKERS):
            return None
        raise ValueError("WHOIS javobi tanilmadi")
    return out


async def _whois_query(server: str, query: str, timeout: float) -> str:
    if not _HOST_RE.fullmatch(server) or not re.fullmatch(r"[a-z0-9.-]{1,253}", query):
        raise ValueError("WHOIS so'rovi yaroqsiz")
    reader, writer = await asyncio.wait_for(asyncio.open_connection(server, 43), timeout)
    try:
        writer.write(f"{query}\r\n".encode("ascii"))
        await writer.drain()
        data = b""
        while len(data) < 65536:
            chunk = await asyncio.wait_for(reader.read(8192), timeout)
            if not chunk:
                break
            data += chunk
        return data.decode("utf-8", "replace")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def _iana_whois_server(tld: str) -> str | None:
    text = await _whois_query("whois.iana.org", tld, 4.0)
    for line in text.splitlines():
        if line.lower().startswith("whois:"):
            srv = line.split(":", 1)[1].strip().lower()
            if _HOST_RE.fullmatch(srv):
                return srv
    return None


class DomainCollector(BaseCollector):
    """Domen / IP bo'yicha ochiq signallar: DNS, WHOIS/RDAP, subdomenlar (CT), ASN."""

    name = "domain"

    async def run(self, query: str) -> list[CollectResult]:
        kind, value = _normalize(query)

        async def _redirect_guard(request: httpx.Request) -> None:
            # SSRF: faqat https va IP-literal bo'lmagan host'lar (rdap.org yo'naltirishlari uchun)
            host = request.url.host
            if request.url.scheme != "https":
                raise httpx.UnsupportedProtocol("faqat https ruxsat etilgan")
            try:
                ipaddress.ip_address(host)
            except ValueError:
                return
            raise httpx.UnsupportedProtocol("IP-literal host ruxsat etilmagan")

        async with httpx.AsyncClient(
            timeout=_RDAP_HTTP_TIMEOUT,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/rdap+json, application/json"},
            follow_redirects=True,
            max_redirects=5,
            event_hooks={"request": [_redirect_guard]},
        ) as client:
            if kind == "ip":
                return await self._run_ip(value, client)
            return await self._run_domain(value, client)

    # ------------------------------------------------------------------ yordamchi

    async def _guard(
        self, coro: Any, timeout: float, source: str, type_: str, value: str
    ) -> list[CollectResult]:
        try:
            out = await asyncio.wait_for(coro, timeout)
            return out if isinstance(out, list) else [out]
        except (asyncio.TimeoutError, TimeoutError):
            msg = _t("c_dom_timeout")
        except Exception as exc:  # bitta manba yiqilsa, qolganlari davom etadi
            msg = _err_text(exc)
        return [_res(source, type_, value, _t("c_dom_check_failed", msg=msg), status="error")]

    # ------------------------------------------------------------------ DOMEN

    async def _run_domain(self, d: str, client: httpx.AsyncClient) -> list[CollectResult]:
        jobs = [
            (self._dns_addr(d), _DNS_TIMEOUT, "DNS A/AAAA", "dns"),
            (self._dns_ns(d), _DNS_TIMEOUT, "DNS NS", "dns"),
            (self._dns_mx(d), _DNS_TIMEOUT, "DNS MX", "dns"),
            (self._dns_spf(d), _DNS_TIMEOUT, "SPF", "dns"),
            (self._dns_dmarc(d), _DNS_TIMEOUT, "DMARC", "dns"),
            (self._whois(d, client), _WHOIS_TIMEOUT, "WHOIS / RDAP", "whois"),
            (self._subdomains(d, client), _CRT_TIMEOUT, _t("c_dom_subs_src"), "subdomain"),
            (self._network(d), _DNS_TIMEOUT, "Hosting / ASN", "network"),
        ]
        groups = await asyncio.gather(
            *(self._guard(c, t, s, ty, d) for c, t, s, ty in jobs)
        )
        return [r for g in groups for r in g]

    async def _dns_addr(self, d: str) -> CollectResult:
        a, aaaa = await asyncio.gather(
            _query(d, "A"), _query(d, "AAAA"), return_exceptions=True
        )
        ips4 = [] if isinstance(a, BaseException) else sorted(r.address for r in a)
        ips6 = [] if isinstance(aaaa, BaseException) else sorted(r.address for r in aaaa)
        if not ips4 and not ips6:
            if isinstance(a, BaseException) and isinstance(aaaa, BaseException):
                raise a
            return _res(
                "DNS A/AAAA", "dns", d,
                _t("c_dom_addr_none"),
                status="not_found",
            )
        parts = []
        if ips4:
            parts.append("A: " + ", ".join(ips4))
        if ips6:
            parts.append("AAAA: " + ", ".join(ips6))
        return _res("DNS A/AAAA", "dns", d, " · ".join(parts), raw={"a": ips4, "aaaa": ips6})

    async def _dns_ns(self, d: str) -> CollectResult:
        recs = await _query(d, "NS")
        hosts = sorted({str(r.target).rstrip(".").lower() for r in recs})
        if not hosts:
            return _res(
                "DNS NS", "dns", d,
                _t("c_dom_ns_none"),
                status="not_found",
            )
        return _res("DNS NS", "dns", d, ", ".join(hosts), raw={"ns": hosts})

    async def _dns_mx(self, d: str) -> CollectResult:
        recs = await _query(d, "MX")
        items = sorted((r.preference, str(r.exchange).rstrip(".").lower()) for r in recs)
        if not items:
            return _res(
                "DNS MX", "dns", d,
                _t("c_dom_mx_none"),
                status="not_found",
            )
        return _res(
            "DNS MX", "dns", d,
            ", ".join(_t("c_dom_mx_item", host=h, priority=p) for p, h in items),
            raw={"mx": [{"priority": p, "host": h} for p, h in items]},
        )

    async def _dns_spf(self, d: str) -> CollectResult:
        recs = [_txt_strings(r) for r in await _query(d, "TXT")]
        spf = [t for t in recs if t.lower().startswith("v=spf1")]
        if not spf:
            return _res(
                "SPF", "dns", d,
                _t("c_dom_spf_none"),
                status="not_found",
            )
        return _res("SPF", "dns", d, spf[0], raw={"spf": spf})

    async def _dns_dmarc(self, d: str) -> CollectResult:
        recs = [_txt_strings(r) for r in await _query(f"_dmarc.{d}", "TXT")]
        dm = [t for t in recs if t.lower().startswith("v=dmarc1")]
        if not dm:
            return _res(
                "DMARC", "dns", d,
                _t("c_dom_dmarc_none"),
                status="not_found",
            )
        return _res("DMARC", "dns", d, dm[0], raw={"dmarc": dm})

    # ------------------------------------------------------------------ WHOIS / RDAP

    async def _rdap_domain(self, d: str, client: httpx.AsyncClient) -> dict[str, Any] | None:
        resp = await client.get(f"https://rdap.org/domain/{d}")
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not isinstance(data, dict):
            return None
        info = _parse_rdap_domain(data)
        if not (info["registrar"] or info["created"] or info["expires"] or info["nameservers"]):
            return None
        return info

    async def _whois(self, d: str, client: httpx.AsyncClient) -> list[CollectResult]:
        info: dict[str, Any] | None = None
        via = "rdap"
        try:
            info = await self._rdap_domain(d, client)
        except Exception:
            info = None

        if info is None:
            via = "whois"
            tld = d.rsplit(".", 1)[1]
            server = await _iana_whois_server(tld)
            if not server:
                return [
                    _res(
                        "WHOIS / RDAP", "whois", d,
                        _t("c_dom_whois_no_server", tld=tld),
                        status="error",
                    )
                ]
            text = await _whois_query(server, d, 5.0)
            info = _parse_whois_text(text)
            if info is None:
                return [
                    _res(
                        "WHOIS / RDAP", "whois", d,
                        _t("c_dom_unregistered"),
                        status="not_found",
                        raw={"via": via, "server": server},
                    )
                ]

        parts = []
        if info["registrar"]:
            parts.append(_t("c_dom_registrar", v=info["registrar"]))
        if info["created"]:
            parts.append(_t("c_dom_created", v=info["created"]))
        if info["expires"]:
            parts.append(_t("c_dom_expires", v=info["expires"]))
        if info["status"]:
            parts.append(_t("c_dom_status", v=", ".join(info["status"][:4])))
        if info["nameservers"]:
            parts.append("NS: " + ", ".join(info["nameservers"][:4]))
        raw = {
            "via": via,
            "registrar": info["registrar"],
            "created": info["created"],
            "updated": info["updated"],
            "expires": info["expires"],
            "status": info["status"],
            "nameservers": info["nameservers"],
        }
        out = [
            _res(
                "WHOIS / RDAP", "whois", d,
                " · ".join(parts) or _t("c_dom_info_found"),
                confidence=0.95,
                raw=raw,
            )
        ]
        exp = _expiry_result(d, info["expires"])
        if exp:
            out.append(exp)
        return out

    # ------------------------------------------------------------------ Subdomenlar

    async def _subdomains(self, d: str, client: httpx.AsyncClient) -> CollectResult:
        url = f"https://crt.sh/?q=%25.{d}&output=json"
        link = f"https://crt.sh/?q=%25.{d}"
        resp = await client.get(url, timeout=12.0)
        if resp.status_code != 200:
            return _res(
                _t("c_dom_subs_src"), "subdomain", d,
                _t("c_dom_crt_http", status=resp.status_code),
                status="error", url=link,
            )
        try:
            rows = resp.json()
        except ValueError:
            return _res(
                _t("c_dom_subs_src"), "subdomain", d,
                _t("c_dom_crt_unreadable"), status="error", url=link,
            )
        names: set[str] = set()
        suffix = "." + d
        for row in rows if isinstance(rows, list) else []:
            for n in str(row.get("name_value", "")).splitlines():
                n = n.strip().lower().rstrip(".")
                if n.startswith("*."):
                    n = n[2:]
                if n != d and n.endswith(suffix) and _DOMAIN_RE.fullmatch(n):
                    names.add(n)
        subs = sorted(names)
        if not subs:
            return _res(
                _t("c_dom_subs_src"), "subdomain", d,
                _t("c_dom_subs_none"),
                status="not_found", url=link,
            )
        shown: list[str] = []
        length = 0
        for s in subs[:15]:
            if length + len(s) + 2 > 450:
                break
            shown.append(s)
            length += len(s) + 2
        detail = ", ".join(shown)
        if len(subs) > len(shown):
            detail += f" ... +{len(subs) - len(shown)}"
        return _res(
            _t("c_dom_subs_src"), "subdomain", _t("c_dom_subs_count", n=len(subs)),
            detail, confidence=0.85, url=link, raw={"subdomains": subs[:200]},
        )

    # ------------------------------------------------------------------ ASN / hosting

    async def _cymru(self, ip: str) -> dict[str, str] | None:
        addr = ipaddress.ip_address(ip)
        if addr.version == 4:
            rev = ".".join(reversed(ip.split(".")))
            name = f"{rev}.origin.asn.cymru.com"
        else:
            nibbles = addr.exploded.replace(":", "")
            name = ".".join(reversed(nibbles)) + ".origin6.asn.cymru.com"
        recs = await _query(name, "TXT")
        if not recs:
            return None
        fields = [f.strip() for f in _txt_strings(recs[0]).split("|")]
        if len(fields) < 3 or not fields[0]:
            return None
        asn = fields[0].split()[0]
        info = {
            "asn": asn,
            "prefix": fields[1],
            "country": fields[2],
            "registry": fields[3] if len(fields) > 3 else "",
            "allocated": fields[4] if len(fields) > 4 else "",
            "as_name": "",
        }
        if asn.isdigit():
            try:
                names = await _query(f"AS{asn}.asn.cymru.com", "TXT")
                if names:
                    f2 = [f.strip() for f in _txt_strings(names[0]).split("|")]
                    info["as_name"] = f2[-1] if len(f2) >= 5 else ""
            except Exception:
                pass
        return info

    @staticmethod
    def _asn_detail(info: dict[str, str]) -> str:
        head = f"AS{info['asn']}" + (f" {info['as_name']}" if info["as_name"] else "")
        return " · ".join(p for p in (head, info["country"], info["prefix"]) if p)

    async def _network(self, d: str) -> CollectResult:
        recs = await _query(d, "A")
        if not recs:
            return _res(
                "Hosting / ASN", "network", d,
                _t("c_dom_net_no_a"), status="not_found",
            )
        ip = sorted(r.address for r in recs)[0]
        info = await self._cymru(ip)
        if not info:
            return _res(
                "Hosting / ASN", "network", d,
                _t("c_dom_net_no_asn", ip=ip), status="not_found",
            )
        return _res(
            "Hosting / ASN", "network", d,
            f"{self._asn_detail(info)} (IP: {ip})",
            raw={"ip": ip, **info},
        )

    # ------------------------------------------------------------------ IP

    async def _run_ip(self, ip: str, client: httpx.AsyncClient) -> list[CollectResult]:
        addr = ipaddress.ip_address(ip)
        kinds = [
            (addr.is_loopback, "Loopback"),
            (addr.is_link_local, "Link-local"),
            (addr.is_multicast, "Multicast"),
            (addr.is_unspecified, _t("c_ip_unspecified")),
            (addr.is_private, _t("c_ip_private")),
            (addr.is_reserved, _t("c_ip_reserved")),
            (not addr.is_global, _t("c_ip_nonglobal")),
        ]
        for flag, label in kinds:
            if flag:
                return [
                    _res(
                        _t("c_ip_kind_src"), "network", ip,
                        _t("c_ip_kind_detail", label=label),
                        status="not_found",
                    )
                ]
        jobs = [
            (self._ptr(ip), _DNS_TIMEOUT, "Reverse DNS (PTR)", "dns"),
            (self._ip_asn(ip), _DNS_TIMEOUT, _t("c_ip_asn_src"), "network"),
            (self._rdap_ip(ip, client), _WHOIS_TIMEOUT, _t("c_ip_rdap_src"), "network"),
        ]
        groups = await asyncio.gather(
            *(self._guard(c, t, s, ty, ip) for c, t, s, ty in jobs)
        )
        return [r for g in groups for r in g]

    async def _ptr(self, ip: str) -> CollectResult:
        name = dns.reversename.from_address(ip)
        recs = await _query(name.to_text(), "PTR")
        hosts = sorted({str(r.target).rstrip(".").lower() for r in recs})
        if not hosts:
            return _res(
                "Reverse DNS (PTR)", "dns", ip,
                _t("c_ip_ptr_none"), status="not_found",
            )
        return _res("Reverse DNS (PTR)", "dns", ip, ", ".join(hosts), raw={"ptr": hosts})

    async def _ip_asn(self, ip: str) -> CollectResult:
        info = await self._cymru(ip)
        if not info:
            return _res(_t("c_ip_asn_src"), "network", ip, _t("c_ip_asn_none"), status="not_found")
        return _res(_t("c_ip_asn_src"), "network", ip, self._asn_detail(info), raw=info)

    async def _rdap_ip(self, ip: str, client: httpx.AsyncClient) -> CollectResult:
        resp = await client.get(f"https://rdap.org/ip/{ip}")
        if resp.status_code == 404:
            return _res(_t("c_ip_rdap_src"), "network", ip, _t("c_ip_rdap_404"), status="not_found")
        if resp.status_code != 200:
            return _res(
                _t("c_ip_rdap_src"), "network", ip,
                _t("c_ip_rdap_http", status=resp.status_code), status="error",
            )
        data = resp.json()
        name = data.get("name")
        handle = data.get("handle")
        country = data.get("country")
        start, end = data.get("startAddress"), data.get("endAddress")
        cidrs = []
        for c in data.get("cidr0_cidrs") or []:
            pref = c.get("v4prefix") or c.get("v6prefix")
            if pref and c.get("length") is not None:
                cidrs.append(f"{pref}/{c['length']}")
        rng = ", ".join(cidrs) if cidrs else (f"{start} - {end}" if start and end else None)

        # Faqat tashkilot (kind=org) nomi; jismoniy shaxs kontaktlari olinmaydi
        org = None
        stack = list(data.get("entities") or [])
        while stack and not org:
            ent = stack.pop(0)
            kind, fn = _vcard_fn(ent)
            if kind == "org" and fn:
                org = fn
            stack.extend(ent.get("entities") or [])

        parts = []
        if name:
            parts.append(_t("c_ip_rdap_name", v=name))
        if rng:
            parts.append(_t("c_ip_rdap_range", v=rng))
        if country:
            parts.append(_t("c_ip_rdap_country", v=country))
        if org:
            parts.append(_t("c_ip_rdap_org", v=org))
        if not parts:
            return _res(_t("c_ip_rdap_src"), "network", ip, _t("c_ip_rdap_empty"), status="not_found")
        return _res(
            _t("c_ip_rdap_src"), "network", ip, " · ".join(parts),
            raw={"name": name, "handle": handle, "range": rng, "country": country, "org": org},
        )
