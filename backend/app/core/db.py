from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Testlarda har test o'z event loop'ida — ulanishlar pool'da qolib ketmasligi uchun NullPool
_pool = {"poolclass": NullPool} if settings.environment == "test" else {}
engine = create_async_engine(settings.database_url, echo=settings.db_echo, future=True, **_pool)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
