from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TgObservation(Base):
    """Telegram akkauntining username holati — platforma o'zi kuzatgan vaqt oralig'i.

    Telegram username tarixini bermaydi, shuning uchun har qidiruvda joriy holat yoziladi:
    usernamelar o'zgarmagan bo'lsa oxirgi qatorning `last_seen` yangilanadi, o'zgargan bo'lsa
    yangi qator ochiladi. O'zgarish vaqti = oldingi qatorning `last_seen` va yangisining
    `first_seen` oralig'i.

    Faqat qidirilgan akkauntlar yoziladi; ism, telefon, bio saqlanmaydi.
    """

    __tablename__ = "tg_observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # user | bot | channel | group
    # faol usernamelar: kichik harfda, alifbo tartibida, vergul bilan; yo'q bo'lsa ""
    usernames: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
