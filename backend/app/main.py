from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, search
from app.core.config import settings
from app.core.db import Base, engine

# Modellar Base.metadata ga ro'yxatdan o'tishi uchun import qilinadi
from app import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev uchun jadvallarni avtomatik yaratamiz. Prod'da Alembic migratsiya ishlatiladi.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(search.router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
