"""Integration tests for tenant APIs and auth flows."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant


async def test_create_tenant_returns_api_key_once(db_client: AsyncClient) -> None:
    response = await db_client.post("/tenants/", json={"name": "Acme"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme"
    assert "api_key" in body
    assert "signing_secret" not in body


async def test_get_current_tenant_returns_authenticated_tenant(
    db_client: AsyncClient,
) -> None:
    create_response = await db_client.post("/tenants/", json={"name": "Acme"})
    api_key = create_response.json()["api_key"]

    response = await db_client.get("/tenants/me/", headers={"X-API-Key": api_key})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Acme"
    assert "signing_secret" in body
    assert "api_key" not in body


async def test_get_current_tenant_returns_401_for_missing_api_key(
    db_client: AsyncClient,
) -> None:
    response = await db_client.get("/tenants/me/")

    assert response.status_code == 401


async def test_get_current_tenant_returns_401_for_invalid_api_key(
    db_client: AsyncClient,
) -> None:
    response = await db_client.get("/tenants/me/", headers={"X-API-Key": "invalid"})

    assert response.status_code == 401


async def test_tenants_receive_distinct_api_keys_and_signing_secrets(
    db_client: AsyncClient,
) -> None:
    first_response = await db_client.post("/tenants/", json={"name": "Acme"})
    second_response = await db_client.post("/tenants/", json={"name": "Globex"})

    first_key = first_response.json()["api_key"]
    second_key = second_response.json()["api_key"]

    first_me = await db_client.get("/tenants/me/", headers={"X-API-Key": first_key})
    second_me = await db_client.get("/tenants/me/", headers={"X-API-Key": second_key})

    assert first_key != second_key
    assert first_me.json()["signing_secret"] != second_me.json()["signing_secret"]


async def test_database_rejects_duplicate_api_keys(
    db_session: AsyncSession,
) -> None:
    first_tenant = Tenant(
        id=uuid.uuid4(),
        name="Acme",
        api_key="duplicate-key",
        signing_secret="secret-one",  # noqa: S106
    )
    second_tenant = Tenant(
        id=uuid.uuid4(),
        name="Globex",
        api_key="duplicate-key",
        signing_secret="secret-two",  # noqa: S106
    )
    db_session.add_all([first_tenant, second_tenant])

    with pytest.raises(IntegrityError):
        await db_session.flush()
