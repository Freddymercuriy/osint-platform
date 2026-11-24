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
    locale: Literal["uz", "uz-Cyrl", "ru", "en"] | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Events (yangiliklar/tadbirlar) ---
class EventImageOut(BaseModel):
    """Hodisa rasmi: imzolangan nisbiy havolalar (1280×720 va 640×360). kind: source (maqolaning o'z rasmi) |
    generated (platforma chizgan illyustratsiya) | fallback (zaxira) | pending (hali tayyorlanmagan — so'rovda chiziladi)."""

    url: str
    thumb: str
    kind: str


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
    # Ustuvorlik (rahbariyat kanali): 0–100, band va sabablar [{code, points, arg?}]
    priority: int | None = None
    priority_band: str | None = None
    priority_reasons: list = []
    # Tarjima (?lang=en|ru|uz berilganda title/summary shu tilda, zanjir: so'ralgan → en → asl)
    source_lang: str | None = None
    display_lang: str | None = None
    translated: bool = False
    translation_status: str | None = None
    original_title: str | None = None
    original_summary: str | None = None
    # Rasm (har hodisada bor — so'rovda chiziladi) va yirik mavzu guruhi (media.rubric)
    image: EventImageOut | None = None
    rubric: str | None = None


class EventsResponse(BaseModel):
    count: int
    items: list[EventItemOut]
