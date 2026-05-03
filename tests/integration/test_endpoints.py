"""Integration tests for webhook endpoint management."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.endpoint import Endpoint


async def test_create_endpoint_returns_endpoint_payload(
    db_client: AsyncClient,
) -> None:
    tenant_response = await db_client.post("/tenants/", json={"name": "Acme"})
    api_key = tenant_response.json()["api_key"]

    response = await db_client.post(
        "/endpoints/",
        json={
            "url": "https://example.com/webhooks/orders",
            "event_types": ["order.created", "order.updated"],
        },
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["url"] == "https://example.com/webhooks/orders"
    assert body["event_types"] == ["order.created", "order.updated"]
    assert body["is_active"] is True
    assert "id" in body
    assert "created_at" in body


async def test_create_endpoint_requires_authentication(
    db_client: AsyncClient,
) -> None:
    response = await db_client.post(
        "/endpoints/",
        json={
            "url": "https://example.com/webhooks/orders",
            "event_types": ["order.created"],
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": "Missing API key.",
        "code": "AUTHENTICATION_FAILED",
    }


async def test_list_endpoints_returns_only_active_endpoints_for_authenticated_tenant(
    db_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    first_tenant_response = await db_client.post("/tenants/", json={"name": "Acme"})
    second_tenant_response = await db_client.post("/tenants/", json={"name": "Globex"})

    first_tenant_id = uuid.UUID(first_tenant_response.json()["id"])
    first_tenant_api_key = first_tenant_response.json()["api_key"]
    second_tenant_id = uuid.UUID(second_tenant_response.json()["id"])

    db_session.add_all(
        [
            Endpoint(
                tenant_id=first_tenant_id,
                url="https://example.com/webhooks/active",
                event_types=["push"],
                is_active=True,
            ),
            Endpoint(
                tenant_id=first_tenant_id,
                url="https://example.com/webhooks/inactive",
                event_types=["issues"],
                is_active=False,
            ),
            Endpoint(
                tenant_id=second_tenant_id,
                url="https://example.com/webhooks/other-tenant",
                event_types=["pull_request"],
                is_active=True,
            ),
        ]
    )
    await db_session.commit()

    response = await db_client.get(
        "/endpoints/",
        headers={"X-API-Key": first_tenant_api_key},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": response.json()[0]["id"],
            "url": "https://example.com/webhooks/active",
            "event_types": ["push"],
            "is_active": True,
            "created_at": response.json()[0]["created_at"],
        }
    ]


async def test_list_endpoints_requires_authentication(
    db_client: AsyncClient,
) -> None:
    response = await db_client.get("/endpoints/")

    assert response.status_code == 401
    assert response.json() == {
        "error": "Missing API key.",
        "code": "AUTHENTICATION_FAILED",
    }


async def test_update_endpoint_updates_url_and_event_types_for_authenticated_tenant(
    db_client: AsyncClient,
) -> None:
    tenant_response = await db_client.post("/tenants/", json={"name": "Acme"})
    api_key = tenant_response.json()["api_key"]
    create_response = await db_client.post(
        "/endpoints/",
        json={
            "url": "https://example.com/webhooks/original",
            "event_types": ["push"],
        },
        headers={"X-API-Key": api_key},
    )
    endpoint_id = create_response.json()["id"]

    response = await db_client.patch(
        f"/endpoints/{endpoint_id}/",
        json={
            "url": "https://example.com/webhooks/updated",
            "event_types": ["push", "pull_request"],
        },
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 200
    assert response.json()["url"] == "https://example.com/webhooks/updated"
    assert response.json()["event_types"] == ["push", "pull_request"]


async def test_update_endpoint_returns_404_for_other_tenant(
    db_client: AsyncClient,
) -> None:
    first_tenant_response = await db_client.post("/tenants/", json={"name": "Acme"})
    second_tenant_response = await db_client.post("/tenants/", json={"name": "Globex"})

    first_api_key = first_tenant_response.json()["api_key"]
    second_api_key = second_tenant_response.json()["api_key"]

    create_response = await db_client.post(
        "/endpoints/",
        json={
            "url": "https://example.com/webhooks/original",
            "event_types": ["push"],
        },
        headers={"X-API-Key": first_api_key},
    )
    endpoint_id = create_response.json()["id"]

    response = await db_client.patch(
        f"/endpoints/{endpoint_id}/",
        json={"event_types": ["issues"]},
        headers={"X-API-Key": second_api_key},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": "Endpoint not found.",
        "code": "ENDPOINT_NOT_FOUND",
    }


async def test_delete_endpoint_soft_deletes_record(
    db_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    tenant_response = await db_client.post("/tenants/", json={"name": "Acme"})
    tenant_id = uuid.UUID(tenant_response.json()["id"])
    api_key = tenant_response.json()["api_key"]

    create_response = await db_client.post(
        "/endpoints/",
        json={
            "url": "https://example.com/webhooks/delete-me",
            "event_types": ["push"],
        },
        headers={"X-API-Key": api_key},
    )
    endpoint_id = uuid.UUID(create_response.json()["id"])

    response = await db_client.delete(
        f"/endpoints/{endpoint_id}/",
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 204

    endpoint = await db_session.get(Endpoint, endpoint_id)
    assert endpoint is not None
    assert endpoint.tenant_id == tenant_id
    assert endpoint.is_active is False


async def test_delete_endpoint_returns_404_for_other_tenant(
    db_client: AsyncClient,
) -> None:
    first_tenant_response = await db_client.post("/tenants/", json={"name": "Acme"})
    second_tenant_response = await db_client.post("/tenants/", json={"name": "Globex"})

    first_api_key = first_tenant_response.json()["api_key"]
    second_api_key = second_tenant_response.json()["api_key"]

    create_response = await db_client.post(
        "/endpoints/",
        json={
            "url": "https://example.com/webhooks/original",
            "event_types": ["push"],
        },
        headers={"X-API-Key": first_api_key},
    )
    endpoint_id = create_response.json()["id"]

    response = await db_client.delete(
        f"/endpoints/{endpoint_id}/",
        headers={"X-API-Key": second_api_key},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": "Endpoint not found.",
        "code": "ENDPOINT_NOT_FOUND",
    }
