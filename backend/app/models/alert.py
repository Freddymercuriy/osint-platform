from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AdminAlert(Base):
    """Adminlar uchun tizim ogohlantirishi (masalan manba bir necha soat ishlamayapti).

    Matn frontendda `kind` bo'yicha tarjima qilinadi; `data` — parametrlar (manba nomi, holati, xato).
    Manba tiklansa `resolved_at` qo'yiladi.
    """

    __tablename__ = "admin_alerts"
    __table_args__ = (Index("ix_admin_alerts_open", "kind", "source_id", "resolved_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # source_down
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
