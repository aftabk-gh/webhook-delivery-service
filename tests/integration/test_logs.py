"""Integration tests for delivery log APIs and queries."""

from datetime import datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.delivery import Delivery
from app.models.endpoint import Endpoint
from app.models.event import Event
from app.models.tenant import Tenant


async def seed_delivery_logs(
    db_session: AsyncSession,
) -> tuple[Tenant, Tenant, Endpoint, Endpoint, list[Delivery]]:
    first_tenant = Tenant(name="Acme")
    second_tenant = Tenant(name="Globex")
    db_session.add_all([first_tenant, second_tenant])
    await db_session.flush()

    first_endpoint = Endpoint(
        tenant_id=first_tenant.id,
        url="https://example.com/webhooks/orders",
        event_types=["order.created"],
    )
    second_endpoint = Endpoint(
        tenant_id=first_tenant.id,
        url="https://example.com/webhooks/invoices",
        event_types=["invoice.paid"],
    )
    other_tenant_endpoint = Endpoint(
        tenant_id=second_tenant.id,
        url="https://example.com/webhooks/other",
        event_types=["order.created"],
    )
    db_session.add_all([first_endpoint, second_endpoint, other_tenant_endpoint])
    await db_session.flush()

    first_event = Event(
        tenant_id=first_tenant.id,
        event_type="order.created",
        payload={"order_id": "ord_123"},
    )
    second_event = Event(
        tenant_id=first_tenant.id,
        event_type="invoice.paid",
        payload={"invoice_id": "inv_123"},
    )
    other_tenant_event = Event(
        tenant_id=second_tenant.id,
        event_type="order.created",
        payload={"order_id": "ord_other"},
    )
    db_session.add_all([first_event, second_event, other_tenant_event])
    await db_session.flush()

    now = datetime(2026, 6, 17, 8, 0, 0)
    deliveries = [
        Delivery(
            tenant_id=first_tenant.id,
            event_id=first_event.id,
            endpoint_id=first_endpoint.id,
            status="success",
            attempt_number=1,
            http_status_code=200,
            latency_ms=10,
            created_at=now,
        ),
        Delivery(
            tenant_id=first_tenant.id,
            event_id=second_event.id,
            endpoint_id=second_endpoint.id,
            status="exhausted",
            attempt_number=3,
            http_status_code=500,
            latency_ms=20,
            created_at=now - timedelta(minutes=1),
        ),
        Delivery(
            tenant_id=first_tenant.id,
            event_id=first_event.id,
            endpoint_id=first_endpoint.id,
            status="pending",
            attempt_number=1,
            http_status_code=None,
            latency_ms=None,
            created_at=now - timedelta(minutes=2),
        ),
        Delivery(
            tenant_id=second_tenant.id,
            event_id=other_tenant_event.id,
            endpoint_id=other_tenant_endpoint.id,
            status="success",
            attempt_number=1,
            http_status_code=200,
            latency_ms=30,
            created_at=now + timedelta(minutes=1),
        ),
    ]
    db_session.add_all(deliveries)
    await db_session.commit()

    return first_tenant, second_tenant, first_endpoint, second_endpoint, deliveries


async def test_list_deliveries_returns_only_authenticated_tenant(
    db_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    first_tenant, _, _, _, deliveries = await seed_delivery_logs(db_session)

    response = await db_client.get(
        "/deliveries/",
        headers={"X-API-Key": first_tenant.api_key},
    )

    assert response.status_code == 200
    body = response.json()
    returned_ids = {item["id"] for item in body["items"]}

    assert returned_ids == {str(delivery.id) for delivery in deliveries[:3]}
    assert body["next_cursor"] is None


async def test_list_deliveries_filters_by_status(
    db_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    first_tenant, _, _, _, deliveries = await seed_delivery_logs(db_session)

    response = await db_client.get(
        "/deliveries/",
        params={"status": "exhausted"},
        headers={"X-API-Key": first_tenant.api_key},
    )

    assert response.status_code == 200
    body = response.json()

    assert [item["id"] for item in body["items"]] == [str(deliveries[1].id)]
    assert body["items"][0]["status"] == "exhausted"


async def test_list_deliveries_filters_by_endpoint(
    db_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    first_tenant, _, first_endpoint, _, deliveries = await seed_delivery_logs(
        db_session
    )

    response = await db_client.get(
        "/deliveries/",
        params={"endpoint_id": str(first_endpoint.id)},
        headers={"X-API-Key": first_tenant.api_key},
    )

    assert response.status_code == 200
    body = response.json()

    assert [item["id"] for item in body["items"]] == [
        str(deliveries[0].id),
        str(deliveries[2].id),
    ]
    assert {item["endpoint_id"] for item in body["items"]} == {str(first_endpoint.id)}


async def test_list_deliveries_paginates_with_cursor(
    db_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    first_tenant, _, _, _, deliveries = await seed_delivery_logs(db_session)

    first_response = await db_client.get(
        "/deliveries/",
        params={"limit": 2},
        headers={"X-API-Key": first_tenant.api_key},
    )

    assert first_response.status_code == 200
    first_body = first_response.json()
    first_page_ids = [item["id"] for item in first_body["items"]]

    assert first_page_ids == [str(deliveries[0].id), str(deliveries[1].id)]
    assert first_body["next_cursor"] is not None

    second_response = await db_client.get(
        "/deliveries/",
        params={"limit": 2, "cursor": first_body["next_cursor"]},
        headers={"X-API-Key": first_tenant.api_key},
    )

    assert second_response.status_code == 200
    second_body = second_response.json()
    second_page_ids = [item["id"] for item in second_body["items"]]

    assert second_page_ids == [str(deliveries[2].id)]
    assert set(first_page_ids).isdisjoint(second_page_ids)
    assert second_body["next_cursor"] is None
