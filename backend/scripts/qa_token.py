"""Smoke-test / QA uchun qisqa muddatli JWT (parol hujjatlarda saqlanmaydi).

    docker-compose exec backend python scripts/qa_token.py --role admin     # birinchi faol admin uchun
    docker-compose exec backend python scripts/qa_token.py --role analyst   # vaqtinchalik qa-analyst@example.com
    docker-compose exec backend python scripts/qa_token.py --role analyst --delete   # QA analyst hisobini o'chirish

Faqat tokenning o'zi chiqariladi (frontend: `TOKEN=$(...) node scripts/qa/smoke.js`). Analyst hisobi tasodifiy parol bilan
yaratiladi, parol hech qayerda ko'rsatilmaydi — kirish faqat shu token orqali.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.db import AsyncSessionLocal  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.models import User  # noqa: E402

QA_ANALYST = "qa-analyst@example.com"


async def main(role: str, minutes: int, delete: bool) -> int:
    async with AsyncSessionLocal() as db:
        if role == "admin":
            user = await db.scalar(
                select(User).where(User.role == "admin", User.is_active).order_by(User.created_at, User.id).limit(1)
            )
            if user is None:
                print("Faol admin yo'q", file=sys.stderr)
                return 1
        else:
            user = await db.scalar(select(User).where(User.email == QA_ANALYST))
            if delete:
                if user is not None:
                    await db.delete(user)
                    await db.commit()
                print("QA analyst o'chirildi", file=sys.stderr)
                return 0
            if user is None:
                user = User(email=QA_ANALYST, hashed_password=hash_password(secrets.token_urlsafe(32)), role="analyst")
                db.add(user)
                await db.commit()
                await db.refresh(user)
        print(create_access_token(str(user.id), expires_minutes=minutes))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=["admin", "analyst"], default="admin")
    ap.add_argument("--minutes", type=int, default=120)
    ap.add_argument("--delete", action="store_true")
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.role, a.minutes, a.delete)))
