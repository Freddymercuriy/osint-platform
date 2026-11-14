"""Admin rolini tayinlash.

Qoida: ADMIN_EMAILS dagi manzillar admin bo'ladi. Ro'yxat bo'sh bo'lsa va bazada umuman admin
yo'q bo'lsa — eng eski faol foydalanuvchi admin qilinadi. Hech kim avtomatik ravishda
analyst'ga tushirilmaydi (admin panelidagi qo'lda o'zgartirishlar saqlanib qoladi).
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import User

log = logging.getLogger("osint.auth")


def role_for_new_user(email: str, users_before: int) -> str:
    if email.lower() in settings.admin_emails_list:
        return "admin"
    if not settings.admin_emails_list and users_before == 0:
        return "admin"  # birinchi foydalanuvchi — platforma egasi
    return "analyst"


async def sync_admin_roles(db: AsyncSession) -> None:
    emails = settings.admin_emails_list
    if emails:
        result = await db.execute(
            update(User)
            .where(func.lower(User.email).in_(emails), User.role != "admin")
            .values(role="admin")
        )
        if result.rowcount:
            log.info("ADMIN_EMAILS: %d ta foydalanuvchi admin qilindi", result.rowcount)
    has_admin = await db.scalar(select(func.count(User.id)).where(User.role == "admin", User.is_active))
    if not has_admin:
        oldest = await db.scalar(
            select(User).where(User.is_active).order_by(User.created_at, User.id).limit(1)
        )
        if oldest is not None:
            oldest.role = "admin"
            log.warning("Admin yo'q edi — eng eski foydalanuvchi (id=%s) admin qilindi", oldest.id)
    await db.commit()
