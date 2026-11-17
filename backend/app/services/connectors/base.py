"""Ulagichlar (connectors) uchun umumiy turlar.

Har manba turi (`sources.kind`) — bitta `Connector` klassi, `@register` bilan ro'yxatga olinadi.
Yangi tur = bitta yangi fayl `app/services/connectors/<kind>.py` (+ `__init__.py` dagi import).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from app.services.connectors.http import HttpFetcher


@dataclass
class RawItem:
    """Ulagich qaytargan bitta element (hali filtrlanmagan, bazaga yozilmagan)."""

    title: str
    url: str
    summary: str = ""
    published: datetime | None = None
    lang: str | None = None  # None → manba tili
    source_name: str | None = None  # ko'rsatiladigan manba nomi (masalan "Reuters (Google News)"); None → manba nomi
    category: str | None = None  # ulagich aniq bilgan kategoriya slug'i (ransomware ...); None → manba / klassifikator
    channel: str = "news"  # news | telegram_channel | telegram_group | api
    scope: str | None = None  # None → manba scope'i
    severity: str | None = None  # ulagich ko'targan daraja (kategoriyadan yuqori bo'lsa)
    countries: list[str] = field(default_factory=list)
    sector: str | None = None
    actor: str | None = None
    matched_keywords: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    dedup_key: str | None = None  # manbalararo bir xil obyekt (masalan ransomware qurboni) uchun kalit
    # Manbaning qat'iy kategoriyasi (sources.category_id) bu elementga qo'llanmaydi — klassifikator hal qiladi
    # (masalan "leak" Telegram chatining mintaqaga oid bo'lmagan global xabari: har gap "leak" 🔔 bo'lmasin)
    ignore_source_category: bool = False


@dataclass
class FetchResult:
    items: list[RawItem]
    http_status: int | None = None
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    state: dict[str, Any] | None = None  # yangilangan kursor holati (None → o'zgarmaydi)
    note: str | None = None  # admin uchun qisqa izoh (masalan "PRO API o'rniga v2 ishlatildi")


# ---------------------------------------------------------------- xatolar → manba holati
class ConnectorError(Exception):
    status = "down"  # manba holati
    outcome = "error"  # source_runs.outcome

    def __init__(self, message: str, http_status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.http_status = http_status
        self.retry_after = retry_after


class SourceBlocked(ConnectorError):
    """403, 429, Cloudflare/CAPTCHA sahifasi. Chetlab o'tilmaydi — manba "blocked" deb belgilanadi."""

    status = "blocked"
    outcome = "blocked"


class RateLimited(SourceBlocked):
    """429 / 503 + Retry-After yoki Telegram FloodWait — keyingi urinish kamida retry_after dan keyin."""

    outcome = "rate_limited"


class AuthMissing(ConnectorError):
    """Kalit yoki login sozlanmagan (yoki rad etildi)."""

    status = "auth_missing"
    outcome = "auth_missing"


class ConfigError(ConnectorError):
    """Manba sozlamasi noto'g'ri (URL yo'q, taqiqlangan manzil ...)."""

    outcome = "config_error"


# ---------------------------------------------------------------- kontekst va bazaviy klass
@dataclass
class SourceView:
    """Ulagichga beriladigan manba ma'lumoti (ORM obyekti emas — sessiyadan mustaqil)."""

    id: int | None
    name: str
    kind: str
    config: dict[str, Any]
    lang: str
    scope: str
    region_filter: bool
    cyber_filter: bool
    api_key_env: str | None
    etag: str | None
    last_modified: str | None
    state: dict[str, Any]
    backfill_days: int
    category_slug: str | None = None


@dataclass
class FetchContext:
    source: SourceView
    http: HttpFetcher
    api_key: str | None = None
    dry_run: bool = False


class Connector:
    kind: ClassVar[str]
    title: ClassVar[str] = ""  # admin panelidagi nom
    # Kalit kerakmi: "required" — kalitsiz ishlamaydi (auth_missing); "optional" — kalit bilan yaxshiroq
    key: ClassVar[str | None] = None
    default_key_env: ClassVar[str | None] = None
    config_fields: ClassVar[tuple[str, ...]] = ()  # config'dagi asosiy maydonlar (admin formasi uchun)
    uses_http: ClassVar[bool] = True

    def validate_config(self, config: dict[str, Any]) -> None:
        """Noto'g'ri sozlama bo'lsa ConfigError."""

    def target_urls(self, source: SourceView) -> list[str]:
        """SSRF tekshiruvi uchun foydalanuvchi kiritgan URL'lar (admin formasi)."""
        return []

    async def fetch(self, ctx: FetchContext) -> FetchResult:  # pragma: no cover - interfeys
        raise NotImplementedError


CONNECTORS: dict[str, type[Connector]] = {}


def register(cls: type[Connector]) -> type[Connector]:
    CONNECTORS[cls.kind] = cls
    return cls


def get_connector(kind: str) -> Connector | None:
    cls = CONNECTORS.get(kind)
    return cls() if cls else None
