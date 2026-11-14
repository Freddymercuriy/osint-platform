import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin_categories, admin_sources, admin_translations, admin_users, auth, stats_v2, events, notifications, search, stats, telegram
from app.core.config import settings
from app.core.db import AsyncSessionLocal, engine
from app.core.errors import register_error_handlers
from app.core.i18n import LangMiddleware
from app.services.admin_roles import sync_admin_roles
from app.services.events import scheduler as events_scheduler

# Modellar Base.metadata ga ro'yxatdan o'tishi uchun import qilinadi
from app import models  # noqa: F401


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


# Production'da standart SECRET_KEY bilan ishga tushmaymiz: kalitni bilgan har kim token yasay oladi
if not settings.is_development and settings.secret_key_is_default:
    raise RuntimeError(
        "SECRET_KEY standart yoki juda qisqa (<32 belgi). backend/.env da tasodifiy kalit bering: "
        "python -c 'import secrets; print(secrets.token_hex(32))'"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sxema Alembic bilan boshqariladi (scripts/start.sh → scripts/migrate.py); create_all yo'q.
    async with AsyncSessionLocal() as db:
        await sync_admin_roles(db)
    events_scheduler.start()  # fon yig'uvchi: har manba o'z jadvali bilan
    yield
    await events_scheduler.stop()
    await engine.dispose()


# debug=False: xato tafsilotlari (traceback) mijozga emas, faqat server logiga yoziladi
app = FastAPI(title=settings.app_name, debug=False, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LangMiddleware)  # Accept-Language → current_lang()
register_error_handlers(app)

app.include_router(auth.router)
app.include_router(search.router)
app.include_router(events.router)
app.include_router(telegram.router)
app.include_router(notifications.router)
app.include_router(stats.router)
app.include_router(stats_v2.router)
app.include_router(admin_sources.router)
app.include_router(admin_categories.router)
app.include_router(admin_translations.router)
app.include_router(admin_users.router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
