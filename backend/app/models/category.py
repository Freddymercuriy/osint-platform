from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

SEVERITIES = ("info", "low", "medium", "high", "critical")
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}


class Category(Base):
    """Hodisa mavzusi (ransomware, leak, phishing ...). Nomlar en/ru/uz; qoidalar — ma'lumot (admin tahrirlaydi).

    `slug` yaratilgandan keyin o'zgarmaydi: `events.category` ustunida denormalizatsiya qilingan.
    `rules`: {"stems": {"en": [...], "ru": [...], "uz": [...], "any": [...]}, "patterns": [regex, ...],
              "weight": 1.0}
    """

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint(
            "severity in ('info', 'low', 'medium', 'high', 'critical')", name="ck_categories_severity"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(96), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(96), nullable=False)
    name_uz: Mapped[str] = mapped_column(String(96), nullable=False)
    description_en: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    description_ru: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    description_uz: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    # Rahbariyat kanali: atama izohi va tavsiya etilgan harakat (uz-Cyrl — uz dan)
    explain_en: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    explain_ru: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    explain_uz: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    action_en: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    action_ru: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    action_uz: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="info", server_default="info", nullable=False)
    color: Mapped[str] = mapped_column(String(32), default="slate", server_default="slate", nullable=False)
    icon: Mapped[str] = mapped_column(String(48), default="Tag", server_default="Tag", nullable=False)
    notify: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = abadiy
    sort_order: Mapped[int] = mapped_column(Integer, default=100, server_default="100", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    rules: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def name(self, lang: str) -> str:
        return getattr(self, f"name_{lang}", None) or self.name_en
