"""Admin: rahbariyat Telegram kanali — kuzatuv ro'yxati, ustuvorlik sozlamalari (keyingi bosqichlarda: kanallar,
navbat, simulyatsiya, ko'rinish).

Kuzatuv ro'yxati yoki og'irliklar o'zgarsa — oxirgi 14 kun hodisalarining ustuvorligi qayta hisoblanadi.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession
from app.core.errors import api_error
from app.models import EventRecord, PublisherSettings, WatchlistEntry
from app.services.publisher import priority as pr
from app.services.publisher import scoring
from app.services.publisher.watchlist import compile_entry, event_texts, match

router = APIRouter(prefix="/api/admin/publisher", tags=["admin-publisher"])

WatchKind = Literal["organisation", "domain", "brand", "product", "person"]
Country = Literal["UZ", "KZ", "KG", "TJ", "TM"]


# ---------------------------------------------------------------- kuzatuv ro'yxati
def clean_aliases(values: list[str]) -> list[str]:
    out: list[str] = []
    for a in values:
        a = " ".join((a or "").split())[:160]
        if len(a) >= 2 and a.lower() not in {x.lower() for x in out}:
            out.append(a)
    return out


class WatchIn(BaseModel):
    kind: WatchKind
    name: str = Field(min_length=2, max_length=160)
    aliases: list[str] = Field(default_factory=list, max_length=50)
    country: Country | None = None
    enabled: bool = True
    notes: str = Field("", max_length=2000)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return " ".join(v.split())

    @field_validator("aliases")
    @classmethod
    def _aliases(cls, v: list[str]) -> list[str]:
        return clean_aliases(v)


class WatchUpdate(BaseModel):
    kind: WatchKind | None = None
    name: str | None = Field(None, min_length=2, max_length=160)
    aliases: list[str] | None = Field(None, max_length=50)
    country: Country | None = None
    enabled: bool | None = None
    notes: str | None = Field(None, max_length=2000)

    @field_validator("aliases")
    @classmethod
    def _aliases(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else clean_aliases(v)


class WatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    name: str
    aliases: list[str]
    country: str | None
    enabled: bool
    notes: str
    terms: list[str] = []  # moslashda ishlatiladigan yozuvlar (lotin ↔ kirill qo'shilgan)
    matches_30d: int | None = None
    created_at: datetime
    updated_at: datetime


def _out(e: WatchlistEntry, matches: int | None = None) -> WatchOut:
    return WatchOut.model_validate(e).model_copy(update={"terms": compile_entry(e).terms, "matches_30d": matches})


async def _get_watch(db, entry_id: int) -> WatchlistEntry:
    e = await db.get(WatchlistEntry, entry_id)
    if e is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "pub_watch_not_found")
    return e


async def _name_taken(db, kind: str, name: str, exclude: int | None = None) -> bool:
    stmt = select(WatchlistEntry.id).where(WatchlistEntry.kind == kind, func.lower(WatchlistEntry.name) == name.lower())
    if exclude is not None:
        stmt = stmt.where(WatchlistEntry.id != exclude)
    return bool(await db.scalar(stmt))


@router.get("/watchlist", response_model=list[WatchOut])
async def list_watch(_: AdminUser, db: DbSession) -> list[WatchOut]:
    rows = (await db.scalars(select(WatchlistEntry).order_by(WatchlistEntry.kind, WatchlistEntry.name))).all()
    return [_out(e) for e in rows]


@router.post("/watchlist", response_model=WatchOut, status_code=status.HTTP_201_CREATED)
async def create_watch(data: WatchIn, _: AdminUser, db: DbSession) -> WatchOut:
    if await _name_taken(db, data.kind, data.name):
        raise api_error(status.HTTP_409_CONFLICT, "pub_watch_name_taken")
    e = WatchlistEntry(**data.model_dump())
    db.add(e)
    await db.commit()
    await scoring.recompute_recent(db)
    await db.refresh(e)
    return _out(e)


@router.patch("/watchlist/{entry_id}", response_model=WatchOut)
async def update_watch(entry_id: int, data: WatchUpdate, _: AdminUser, db: DbSession) -> WatchOut:
    e = await _get_watch(db, entry_id)
    changes = data.model_dump(exclude_unset=True)
    kind, name = changes.get("kind") or e.kind, changes.get("name") or e.name
    if ("kind" in changes or "name" in changes) and await _name_taken(db, kind, name, exclude=e.id):
        raise api_error(status.HTTP_409_CONFLICT, "pub_watch_name_taken")
    for k, v in changes.items():
        if v is not None or k == "country":
            setattr(e, k, v)
    await db.commit()
    await scoring.recompute_recent(db)
    await db.refresh(e)
    return _out(e)


@router.delete("/watchlist/{entry_id}")
async def delete_watch(entry_id: int, _: AdminUser, db: DbSession) -> dict[str, int]:
    e = await _get_watch(db, entry_id)
    await db.delete(e)
    await db.commit()
    changed = await scoring.recompute_recent(db)
    return {"deleted": entry_id, "recomputed": changed}


class WatchMatch(BaseModel):
    id: int
    title: str
    source: str
    first_seen: datetime
    scope: str
    priority: int | None
    priority_band: str | None


class WatchTestOut(BaseModel):
    terms: list[str]
    total: int
    items: list[WatchMatch]


class WatchTestIn(BaseModel):
    """Saqlanmagan (tahrirlanayotgan) yozuvni sinash."""

    kind: WatchKind
    name: str = Field(min_length=2, max_length=160)
    aliases: list[str] = Field(default_factory=list, max_length=50)


async def _test_entry(db, entry, days: int) -> WatchTestOut:
    cw = compile_entry(entry)
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (await db.scalars(
        select(EventRecord).where(EventRecord.first_seen >= since).order_by(EventRecord.first_seen.desc())
    )).all()
    trs = await scoring._translations(db, [r.id for r in rows])
    hits = [r for r in rows if match([cw], event_texts(r.title, r.summary, r.matched_keywords, r.extra,
                                                       trs.get(r.id, ())))]
    return WatchTestOut(terms=cw.terms, total=len(hits), items=[
        WatchMatch(id=r.id, title=r.title[:300], source=r.source, first_seen=r.first_seen, scope=r.scope,
                   priority=r.priority, priority_band=r.priority_band) for r in hits[:50]])


@router.get("/watchlist/{entry_id}/test", response_model=WatchTestOut)
async def test_watch(entry_id: int, _: AdminUser, db: DbSession,
                     days: int = Query(30, ge=1, le=90)) -> WatchTestOut:
    """Oxirgi `days` kundagi qaysi hodisalarga mos kelardi (hech narsa saqlanmaydi)."""
    return await _test_entry(db, await _get_watch(db, entry_id), days)


@router.post("/watchlist/test", response_model=WatchTestOut)
async def test_watch_draft(data: WatchTestIn, _: AdminUser, db: DbSession,
                           days: int = Query(30, ge=1, le=90)) -> WatchTestOut:
    return await _test_entry(db, WatchlistEntry(kind=data.kind, name=data.name, aliases=clean_aliases(data.aliases)),
                             days)


# ---------------------------------------------------------------- ustuvorlik sozlamalari
class SeverityWeights(BaseModel):
    critical: int = Field(ge=0, le=100)
    high: int = Field(ge=0, le=100)
    medium: int = Field(ge=0, le=100)
    low: int = Field(ge=0, le=100)
    info: int = Field(ge=0, le=100)


Sector = Literal["government", "finance", "telecom", "energy", "healthcare", "education", "transport"]


class Weights(BaseModel):
    severity: SeverityWeights
    country_uz: int = Field(ge=0, le=100)
    country_ca: int = Field(ge=0, le=100)
    sector: int = Field(ge=0, le=100)
    sectors: list[Sector] = Field(max_length=10)
    watch_org: int = Field(ge=0, le=100)
    watch_product: int = Field(ge=0, le=100)
    watch_person: int = Field(ge=0, le=100)
    official: int = Field(ge=0, le=100)
    extra_source: int = Field(ge=0, le=50)
    extra_source_max: int = Field(ge=0, le=5)
    records_100k: int = Field(ge=0, le=50)
    records_1m: int = Field(ge=0, le=50)
    stale: int = Field(ge=-100, le=0)
    stale_hours: int = Field(ge=1, le=24 * 30)
    underground_only: int = Field(ge=-100, le=0)


class Bands(BaseModel):
    critical: int = Field(ge=1, le=100)
    high: int = Field(ge=1, le=100)
    medium: int = Field(ge=1, le=100)

    @field_validator("medium")
    @classmethod
    def _order(cls, v: int, info) -> int:
        d = info.data
        if not (v < d.get("high", 101) < d.get("critical", 102)):
            raise ValueError("bands: medium < high < critical")
        return v


class ScoringSettings(BaseModel):
    weights: Weights
    bands: Bands
    defaults: dict | None = None
    updated_at: datetime | None = None


@router.get("/settings", response_model=ScoringSettings)
async def get_settings(_: AdminUser, db: DbSession) -> ScoringSettings:
    w, b = await scoring.load_settings(db)
    row = await db.get(PublisherSettings, 1)
    return ScoringSettings(weights=Weights.model_validate(w), bands=Bands.model_validate(b),
                           defaults={"weights": pr.DEFAULT_WEIGHTS, "bands": pr.DEFAULT_BANDS},
                           updated_at=row.updated_at if row else None)


class SettingsIn(BaseModel):
    weights: Weights
    bands: Bands


@router.put("/settings", response_model=ScoringSettings)
async def put_settings(data: SettingsIn, admin: AdminUser, db: DbSession) -> ScoringSettings:
    row = await db.get(PublisherSettings, 1)
    if row is None:
        row = PublisherSettings(id=1, weights={}, bands={})
        db.add(row)
    row.weights, row.bands, row.updated_by = data.weights.model_dump(), data.bands.model_dump(), admin.id
    row.updated_at = datetime.now(UTC)
    await db.commit()
    await scoring.recompute_recent(db)
    return await get_settings(admin, db)
