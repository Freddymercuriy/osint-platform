from datetime import datetime

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
    created_at: datetime


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
    status: str = "found"
    confidence: float = 1.0


class SearchResponse(BaseModel):
    job_id: int
    query: str
    kind: str
    checked: int  # tekshirilgan manbalar soni
    found: int  # topilgan profillar soni
    results: list[CollectResultOut]


class SearchJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    query: str
    status: str
    created_at: datetime
