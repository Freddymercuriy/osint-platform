"""users.role (admin | analyst) va users.locale

Admin tayinlash ilova ishga tushganda (`services/admin_roles.py`): ADMIN_EMAILS dagi manzillar,
ular bo'lmasa — eng eski faol foydalanuvchi.

Revision ID: 0002_user_roles
Revises: 0001_baseline
Create Date: 2026-11-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_user_roles"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(16), server_default="analyst", nullable=False))
    op.add_column("users", sa.Column("locale", sa.String(8), nullable=True))
    op.create_check_constraint("ck_users_role", "users", "role in ('admin', 'analyst')")


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "locale")
    op.drop_column("users", "role")
