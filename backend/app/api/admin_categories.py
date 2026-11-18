"""Kategoriyalar: hamma uchun ro'yxat (`/api/categories`) va admin CRUD, tartiblash, qayta tasniflash."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from sqlalchemy import func, select

from app.core.errors import api_error
from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models import Category, EventRecord
from app.services.events.categories import apply_category_severity, move_events_to_other, reclassify
from app.services.events.classifier import FALLBACK, RuleError, validate_rules
from app.services.i18n.text import uz_to_cyrillic

router = APIRouter(tags=["categories"])

Severity = Literal["info", "low", "medium", "high", "critical"]
COLORS = ("red", "orange", "amber", "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue", "indigo",
          "violet", "purple", "fuchsia", "pink", "rose", "slate")
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
ICON_PATTERN = r"^[A-Z][A-Za-z0-9]{1,47}$"


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name_en: str
    name_ru: str
    name_uz: str
    description_en: str
    description_ru: str
    description_uz: str
    severity: str
    color: str
    icon: str
    notify: bool
    retention_days: int | None
    sort_order: int
    enabled: bool
    is_system: bool
    event_count: int = 0

    # O'zbek kirill interfeysi uchun (latin.jaybi.uz dvigateli; bazada saqlanmaydi — name_uz dan hisoblanadi)
    @computed_field  # type: ignore[prop-decorator]
    @property
    def name_uz_cyrl(self) -> str:
        return uz_to_cyrillic(self.name_uz)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def description_uz_cyrl(self) -> str:
        return uz_to_cyrillic(self.description_uz)


class CategoryAdminOut(CategoryOut):
    rules: dict[str, Any]
    # Rahbariyat kanali: atama izohi va tavsiya (uz-Cyrl — uz dan hosil qilinadi)
    explain_en: str = ""
    explain_ru: str = ""
    explain_uz: str = ""
    action_en: str = ""
    action_ru: str = ""
    action_uz: str = ""
    created_at: datetime
    updated_at: datetime


class CategoryBase(BaseModel):
    name_en: str = Field(min_length=1, max_length=96)
    name_ru: str = Field(min_length=1, max_length=96)
    name_uz: str = Field(min_length=1, max_length=96)
    description_en: str = Field("", max_length=1000)
    description_ru: str = Field("", max_length=1000)
    description_uz: str = Field("", max_length=1000)
    severity: Severity = "info"
    color: str = "slate"
    icon: str = Field("Tag", pattern=ICON_PATTERN)
    notify: bool = False
    retention_days: int | None = Field(None, ge=1, le=3650)
    sort_order: int = Field(500, ge=0, le=100000)
    enabled: bool = True
    rules: dict[str, Any] = Field(default_factory=dict)
    explain_en: str = Field("", max_length=600)
    explain_ru: str = Field("", max_length=600)
    explain_uz: str = Field("", max_length=600)
    action_en: str = Field("", max_length=600)
    action_ru: str = Field("", max_length=600)
    action_uz: str = Field("", max_length=600)

    @field_validator("color")
    @classmethod
    def _color(cls, v: str) -> str:
        if v not in COLORS:
            raise ValueError(f"color — {', '.join(COLORS)} dan biri")
        return v

    @field_validator("rules")
    @classmethod
    def _rules(cls, v: dict) -> dict:
        try:
            return validate_rules(v or {})
        except RuleError as exc:
            raise ValueError(str(exc)) from exc


class CategoryIn(CategoryBase):
    slug: str = Field(min_length=2, max_length=48, pattern=SLUG_PATTERN)


class CategoryUpdate(BaseModel):
    """Qisman yangilash. `slug` o'zgarmaydi (hodisalarda denormalizatsiya qilingan)."""

    name_en: str | None = Field(None, min_length=1, max_length=96)
    name_ru: str | None = Field(None, min_length=1, max_length=96)
    name_uz: str | None = Field(None, min_length=1, max_length=96)
    description_en: str | None = Field(None, max_length=1000)
    description_ru: str | None = Field(None, max_length=1000)
    description_uz: str | None = Field(None, max_length=1000)
    severity: Severity | None = None
    color: str | None = None
    icon: str | None = Field(None, pattern=ICON_PATTERN)
    notify: bool | None = None
    retention_days: int | None = Field(None, ge=1, le=3650)
    sort_order: int | None = Field(None, ge=0, le=100000)
    enabled: bool | None = None
    rules: dict[str, Any] | None = None
    explain_en: str | None = Field(None, max_length=600)
    explain_ru: str | None = Field(None, max_length=600)
    explain_uz: str | None = Field(None, max_length=600)
    action_en: str | None = Field(None, max_length=600)
    action_ru: str | None = Field(None, max_length=600)
    action_uz: str | None = Field(None, max_length=600)

    @field_validator("color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        if v is not None and v not in COLORS:
            raise ValueError(f"color — {', '.join(COLORS)} dan biri")
        return v

    @field_validator("rules")
    @classmethod
    def _rules(cls, v: dict | None) -> dict | None:
        if v is None:
            return None
        try:
            return validate_rules(v)
        except RuleError as exc:
            raise ValueError(str(exc)) from exc


async def _counts(db) -> dict[int, int]:
    return dict((await db.execute(
        select(EventRecord.category_id, func.count(EventRecord.id)).group_by(EventRecord.category_id)
    )).all())


async def _get(db, category_id: int) -> Category:
    c = await db.get(Category, category_id)
    if c is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "category_not_found")
    return c


# ---------------------------------------------------------------- hamma uchun
@router.get("/api/categories", response_model=list[CategoryOut])
async def list_categories(_: CurrentUser, db: DbSession, include_disabled: bool = False) -> list[CategoryOut]:
    stmt = select(Category).order_by(Category.sort_order, Category.id)
    if not include_disabled:
        stmt = stmt.where(Category.enabled)
    counts = await _counts(db)
    return [CategoryOut.model_validate(c).model_copy(update={"event_count": counts.get(c.id, 0)})
            for c in (await db.scalars(stmt)).all()]


# ---------------------------------------------------------------- admin
@router.get("/api/admin/categories", response_model=list[CategoryAdminOut])
async def admin_list(_: AdminUser, db: DbSession) -> list[CategoryAdminOut]:
    counts = await _counts(db)
    rows = (await db.scalars(select(Category).order_by(Category.sort_order, Category.id))).all()
    return [CategoryAdminOut.model_validate(c).model_copy(update={"event_count": counts.get(c.id, 0)}) for c in rows]


@router.get("/api/admin/categories/{category_id}", response_model=CategoryAdminOut)
async def admin_get(category_id: int, _: AdminUser, db: DbSession) -> CategoryAdminOut:
    c = await _get(db, category_id)
    return CategoryAdminOut.model_validate(c).model_copy(update={"event_count": (await _counts(db)).get(c.id, 0)})


@router.post("/api/admin/categories", response_model=CategoryAdminOut, status_code=status.HTTP_201_CREATED)
async def admin_create(data: CategoryIn, _: AdminUser, db: DbSession) -> CategoryAdminOut:
    if await db.scalar(select(Category.id).where(Category.slug == data.slug)):
        raise api_error(status.HTTP_409_CONFLICT, "slug_taken")
    c = Category(**data.model_dump(), is_system=False)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return CategoryAdminOut.model_validate(c)


@router.patch("/api/admin/categories/{category_id}", response_model=CategoryAdminOut)
async def admin_update(category_id: int, data: CategoryUpdate, _: AdminUser, db: DbSession) -> CategoryAdminOut:
    c = await _get(db, category_id)
    changes = data.model_dump(exclude_unset=True)
    if c.slug == FALLBACK and changes.get("enabled") is False:
        raise api_error(status.HTTP_409_CONFLICT, "category_other_protected")
    for k, v in changes.items():
        setattr(c, k, v)
    if "severity" in changes:
        await apply_category_severity(db, c)
    await db.commit()
    if "severity" in changes:  # hodisa jiddiyligi o'zgardi → ustuvorlik (oxirgi 14 kun)
        from app.services.publisher.scoring import recompute_recent

        await recompute_recent(db)
    await db.refresh(c)
    return CategoryAdminOut.model_validate(c).model_copy(update={"event_count": (await _counts(db)).get(c.id, 0)})


@router.delete("/api/admin/categories/{category_id}")
async def admin_delete(category_id: int, _: AdminUser, db: DbSession) -> dict[str, int]:
    """Hodisalari `other` ga o'tadi. Tizim kategoriyalarini faqat o'chirib (disable) qo'yish mumkin."""
    c = await _get(db, category_id)
    if c.is_system:
        raise api_error(status.HTTP_409_CONFLICT, "category_system_protected")
    moved = await move_events_to_other(db, c)
    await db.delete(c)
    await db.commit()
    if moved:
        from app.services.publisher.scoring import recompute_recent

        await recompute_recent(db)
    return {"moved_to_other": moved}


class ReorderIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


@router.post("/api/admin/categories/reorder", response_model=list[CategoryAdminOut])
async def admin_reorder(data: ReorderIn, _: AdminUser, db: DbSession) -> list[CategoryAdminOut]:
    rows = {c.id: c for c in (await db.scalars(select(Category))).all()}
    if set(data.ids) - set(rows) or len(set(data.ids)) != len(data.ids):
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "ids_invalid")
    for i, cid in enumerate(data.ids):
        rows[cid].sort_order = (i + 1) * 10
    other = next((c for c in rows.values() if c.slug == FALLBACK), None)
    if other is not None and other.id not in data.ids:  # ro'yxatda bo'lmasa 'other' oxirida qoladi
        other.sort_order = max(c.sort_order for c in rows.values()) + 1000
    await db.commit()
    return await admin_list(_, db)


class ReclassifyOut(BaseModel):
    dry_run: bool
    considered: int
    changed: int
    severity_changed: int
    locked_skipped: int
    transitions: dict[str, int]
    samples: list[dict]


@router.post("/api/admin/categories/reclassify", response_model=ReclassifyOut)
async def admin_reclassify(_: AdminUser, db: DbSession, dry_run: bool = Query(True)) -> ReclassifyOut:
    """Qoidalarni saqlangan hodisalarga qo'llash. Avval `dry_run=true` (standart) — nechtasi o'zgarishini ko'rsatadi."""
    r = await reclassify(db, dry_run=dry_run)
    if not dry_run and (r.changed or r.severity_changed):
        from app.services.publisher.scoring import recompute_recent

        await recompute_recent(db)
    return ReclassifyOut(dry_run=dry_run, considered=r.considered, changed=r.changed,
                         severity_changed=r.severity_changed, locked_skipped=r.locked_skipped,
                         transitions=dict(r.transitions.most_common()), samples=r.samples)
