from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    isolation_level="READ COMMITTED",
)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

sync_engine = create_engine(
    settings.sync_database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    isolation_level="READ COMMITTED",
)

SessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False, class_=Session)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
