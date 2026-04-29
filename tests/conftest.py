from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app


class TestSettings(BaseSettings):
    """Settings used by the test suite."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    test_database_url: str | None = None


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[AsyncClient]:
    """HTTP client for app-level tests that do not require DB overrides."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Dedicated database URL for integration tests."""
    database_url = TestSettings().test_database_url
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for DB-backed integration tests.")
    return database_url


@pytest_asyncio.fixture
async def test_engine(test_database_url: str) -> AsyncGenerator[AsyncEngine]:
    """Async engine for DB-backed integration tests."""
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Isolated session per test with fresh schema state."""
    async with test_engine.begin() as connection:
        await connection.run_sync(lambda conn: Base.metadata.drop_all(bind=conn))
        await connection.run_sync(lambda conn: Base.metadata.create_all(bind=conn))

    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    session = session_factory()

    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        async with test_engine.begin() as connection:
            await connection.run_sync(lambda conn: Base.metadata.drop_all(bind=conn))


@pytest_asyncio.fixture
async def db_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """HTTP client that routes app DB dependencies to the test session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
