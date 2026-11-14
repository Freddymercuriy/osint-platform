"""events.uid — yangi formula: sha256(manba nomi | URL | sarlavha), kategoriyasiz

v1 da uid kategoriyani ham o'z ichiga olardi; v2 da kategoriya klassifikator bilan o'zgarishi mumkin,
shuning uchun uid unga bog'liq bo'lmasligi kerak (aks holda bir xil element qayta yozilardi).
Ikki qator bir xil yangi uid ga tushsa — eskisi yangi uid oladi, ikkinchisi eski uid bilan qoladi.
Downgrade: v1 formulasi (category | source | title | url) qayta hisoblanadi.

Revision ID: 0005_event_uid_v2
Revises: 0004_seed_sources
Create Date: 2026-11-14
"""
import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_event_uid_v2"
down_revision: str | None = "0004_seed_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _sha(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _rewrite(make) -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("select id, uid, source, category, title, url from events order by id")).all()
    taken = {r.uid for r in rows}
    for r in rows:
        new = make(r)
        if new == r.uid or new in taken:
            continue
        taken.discard(r.uid)
        taken.add(new)
        conn.execute(sa.text("update events set uid = :u where id = :id"), {"u": new, "id": r.id})


def upgrade() -> None:
    _rewrite(lambda r: _sha(f"{r.source}|{r.url}|{r.title}"))


def downgrade() -> None:
    _rewrite(lambda r: _sha(f"{r.category}|{r.source}|{r.title}|{r.url}"))
