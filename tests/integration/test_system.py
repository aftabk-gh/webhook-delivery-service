from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from redis.exceptions import RedisError

from app.core.redis import redis_client
from app.database import engine
from app.main import (
    app as fastapi_app,
    lifespan,
)


async def test_health_returns_ok_when_redis_is_available(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(redis_client, "ping", AsyncMock(return_value=True))

    response = await api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "webhook-delivery-service",
        "redis": "ok",
    }


async def test_health_reports_unavailable_when_redis_ping_fails(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(redis_client, "ping", AsyncMock(side_effect=RedisError("down")))

    response = await api_client.get("/health")

    assert response.status_code == 200
    assert response.json()["redis"] == "unavailable"


async def test_lifespan_does_not_crash_when_redis_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.main.verify_redis", AsyncMock(side_effect=RedisError("down"))
    )
    monkeypatch.setattr(redis_client, "aclose", AsyncMock(return_value=None))

    async with lifespan(fastapi_app):
        pass


def test_database_engine_uses_read_committed_isolation() -> None:
    assert engine.sync_engine.dialect._on_connect_isolation_level == "READ COMMITTED"
