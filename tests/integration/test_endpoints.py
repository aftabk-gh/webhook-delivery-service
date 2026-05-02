"""Integration tests for webhook endpoint management."""

from httpx import AsyncClient


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
