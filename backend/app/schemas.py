from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Auth ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    role: str = "analyst"
    locale: str | None = None
    created_at: datetime


class UserUpdate(BaseModel):
    locale: Literal["uz", "ru", "en"] | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- OSINT qidiruv ---
class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=256)


class CollectResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    type: str
    value: str
    url: str | None = None
    detail: str | None = None
    status: str = "found"
    confidence: float = 1.0


class SearchResponse(BaseModel):
    job_id: int
    query: str
    kind: str
    checked: int  # tekshirilgan manbalar soni
    found: int  # topilgan profillar soni
    created_at: datetime | None = None
    results: list[CollectResultOut]


class SearchJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    query: str
    status: str
    created_at: datetime
    checked: int = 0  # tekshirilgan manbalar soni
    found: int = 0  # topilganlar soni


# --- Hisobot eksporti ---
class ReportMeta(BaseModel):
    platform: str
    format_version: int = 1
    generated_at: datetime
    notice: str


class ReportJob(BaseModel):
    id: int
    kind: str
    query: str
    status: str
    created_at: datetime


class ReportSummary(BaseModel):
    checked: int
    found: int
    not_found: int
    error: int


class JobReport(BaseModel):
    """Bitta qidiruvning eksport qilinadigan hisoboti (JSON fayl / chop etish sahifasi)."""

    report: ReportMeta
    job: ReportJob
    summary: ReportSummary
    results: list[CollectResultOut]


# --- Events (yangiliklar/tadbirlar) ---
class EventItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    first_seen: datetime | None = None
    source: str
    title: str
    url: str
    summary: str
    published: datetime | None = None
    lang: str
    category: str  # kategoriya slug'i (v1 bilan mos)
    # v2
    source_id: int | None = None
    category_id: int | None = None
    channel: str = "news"
    scope: str = "regional"
    severity: str = "info"
    countries: list[str] = []
    sector: str | None = None
    actor: str | None = None
    matched_keywords: list[str] = []
    extra: dict = {}
    also_reported_by: list = []
    is_baseline: bool = False
    # Tarjima (?lang=en|ru|uz berilganda title/summary shu tilda, zanjir: so'ralgan → en → asl)
    source_lang: str | None = None
    display_lang: str | None = None
    translated: bool = False
    translation_status: str | None = None
    original_title: str | None = None
    original_summary: str | None = None


class EventsResponse(BaseModel):
    count: int
    items: list[EventItemOut]
