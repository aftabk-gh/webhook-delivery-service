from collections.abc import AsyncIterator
from typing import cast

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_tenant
from app.database import get_db
from app.main import app
from app.models import Tenant


async def override_current_tenant() -> Tenant:
    return Tenant(name="Acme")


async def override_db() -> AsyncIterator[AsyncSession]:
    yield cast(AsyncSession, None)


async def test_create_event_requires_authentication(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/events/",
        json={
            "event_type": "order.created",
            "payload": {"order_id": "ord_123"},
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": "Missing API key.",
        "code": "AUTHENTICATION_FAILED",
    }


async def test_create_event_rejects_missing_event_type(
    api_client: AsyncClient,
) -> None:
    app.dependency_overrides[get_current_tenant] = override_current_tenant
    app.dependency_overrides[get_db] = override_db

    try:
        response = await api_client.post(
            "/events/",
            json={"payload": {"order_id": "ord_123"}},
            headers={"X-API-Key": "test-api-key"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json().get("code") == "VALIDATION_ERROR"


async def test_create_event_rejects_payload_over_256kb(
    api_client: AsyncClient,
) -> None:
    app.dependency_overrides[get_current_tenant] = override_current_tenant
    app.dependency_overrides[get_db] = override_db

    try:
        response = await api_client.post(
            "/events/",
            json={
                "event_type": "order.created",
                "payload": {"data": "x" * (256 * 1024)},
            },
            headers={"X-API-Key": "test-api-key"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {
        "error": "Event payload must be 256KB or smaller.",
        "code": "EVENT_PAYLOAD_TOO_LARGE",
    }
