"""Integration tests for delivery worker behavior."""

from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.delivery import Delivery
from app.models.endpoint import Endpoint
from app.models.event import Event
from app.models.tenant import Tenant
from app.services import delivery as delivery_service


def patch_delivery_session_factory(
    monkeypatch: pytest.MonkeyPatch,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    monkeypatch.setattr(delivery_service, "AsyncSessionLocal", session_factory)


async def create_tenant_event_and_endpoints(
    db_session: AsyncSession,
) -> tuple[Tenant, Event, Endpoint, Endpoint, Endpoint, Endpoint]:
    tenant = Tenant(name="Acme")
    other_tenant = Tenant(name="Globex")
    db_session.add_all([tenant, other_tenant])
    await db_session.flush()

    event = Event(
        tenant_id=tenant.id,
        event_type="order.created",
        payload={"order_id": "ord_123"},
        idempotency_key="evt_ord_123",
    )
    matching_endpoint = Endpoint(
        tenant_id=tenant.id,
        url="https://example.com/webhooks/matching",
        event_types=["order.created", "order.updated"],
        is_active=True,
    )
    inactive_endpoint = Endpoint(
        tenant_id=tenant.id,
        url="https://example.com/webhooks/inactive",
        event_types=["order.created"],
        is_active=False,
    )
    non_matching_endpoint = Endpoint(
        tenant_id=tenant.id,
        url="https://example.com/webhooks/non-matching",
        event_types=["invoice.paid"],
        is_active=True,
    )
    other_tenant_endpoint = Endpoint(
        tenant_id=other_tenant.id,
        url="https://example.com/webhooks/other-tenant",
        event_types=["order.created"],
        is_active=True,
    )
    db_session.add_all(
        [
            event,
            matching_endpoint,
            inactive_endpoint,
            non_matching_endpoint,
            other_tenant_endpoint,
        ]
    )
    await db_session.commit()

    return (
        tenant,
        event,
        matching_endpoint,
        inactive_endpoint,
        non_matching_endpoint,
        other_tenant_endpoint,
    )


async def test_fan_out_event_deliveries_creates_delivery_for_matching_endpoint(
    db_session: AsyncSession,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_delivery_session_factory(monkeypatch, test_engine)
    tenant, event, matching_endpoint, *_ = await create_tenant_event_and_endpoints(
        db_session
    )
    dispatched_tasks: list[tuple[list[str], str]] = []

    def dispatch_delivery(*, args: list[str], queue: str) -> None:
        dispatched_tasks.append((args, queue))

    await delivery_service.fan_out_event_deliveries(
        event_id=str(event.id),
        tenant_id=str(tenant.id),
        dispatch_delivery=dispatch_delivery,
    )

    delivery = (
        await db_session.execute(
            select(Delivery).where(
                Delivery.tenant_id == tenant.id,
                Delivery.event_id == event.id,
            )
        )
    ).scalar_one()

    assert delivery.endpoint_id == matching_endpoint.id
    assert delivery.status == "pending"
    assert dispatched_tasks == [([str(delivery.id), str(tenant.id)], "delivery")]


async def test_fan_out_event_deliveries_ignores_inactive_non_matching_and_cross_tenant_endpoints(
    db_session: AsyncSession,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_delivery_session_factory(monkeypatch, test_engine)
    tenant, event, matching_endpoint, *_ = await create_tenant_event_and_endpoints(
        db_session
    )

    await delivery_service.fan_out_event_deliveries(
        event_id=str(event.id),
        tenant_id=str(tenant.id),
        dispatch_delivery=lambda **_: None,
    )

    deliveries = list(
        (
            await db_session.execute(
                select(Delivery).where(
                    Delivery.tenant_id == tenant.id,
                    Delivery.event_id == event.id,
                )
            )
        )
        .scalars()
        .all()
    )
    delivery_count = await db_session.scalar(select(func.count()).select_from(Delivery))

    assert delivery_count == 1
    assert [delivery.endpoint_id for delivery in deliveries] == [matching_endpoint.id]


async def test_deliver_to_endpoint_once_marks_success_after_200_response(
    db_session: AsyncSession,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_delivery_session_factory(monkeypatch, test_engine)
    tenant, event, endpoint, *_ = await create_tenant_event_and_endpoints(db_session)
    delivery = Delivery(
        tenant_id=tenant.id,
        event_id=event.id,
        endpoint_id=endpoint.id,
        status="pending",
    )
    db_session.add(delivery)
    await db_session.commit()
    delivery_id = delivery.id
    endpoint_url = endpoint.url
    event_payload = event.payload
    event_id = event.id
    event_type = event.event_type

    posted: dict[str, Any] = {}
    patch_http_client(monkeypatch, status_code=200, text="ok", posted=posted)

    await delivery_service.deliver_to_endpoint_once(
        delivery_id=str(delivery_id),
        tenant_id=str(tenant.id),
    )

    db_session.expire_all()
    saved_delivery = await db_session.get(Delivery, delivery_id)

    assert saved_delivery is not None
    assert saved_delivery.status == "success"
    assert saved_delivery.http_status_code == 200
    assert saved_delivery.response_body == "ok"
    assert saved_delivery.latency_ms is not None
    assert posted["url"] == endpoint_url
    assert posted["json"] == event_payload
    assert posted["headers"]["X-Webhook-Event-ID"] == str(event_id)
    assert posted["headers"]["X-Webhook-Event-Type"] == event_type


async def test_deliver_to_endpoint_once_marks_failed_after_500_response(
    db_session: AsyncSession,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_delivery_session_factory(monkeypatch, test_engine)
    tenant, event, endpoint, *_ = await create_tenant_event_and_endpoints(db_session)
    delivery = Delivery(
        tenant_id=tenant.id,
        event_id=event.id,
        endpoint_id=endpoint.id,
        status="pending",
    )
    db_session.add(delivery)
    await db_session.commit()
    delivery_id = delivery.id

    patch_http_client(monkeypatch, status_code=500, text="server error")

    await delivery_service.deliver_to_endpoint_once(
        delivery_id=str(delivery_id),
        tenant_id=str(tenant.id),
    )

    db_session.expire_all()
    saved_delivery = await db_session.get(Delivery, delivery_id)

    assert saved_delivery is not None
    assert saved_delivery.status == "failed"
    assert saved_delivery.http_status_code == 500
    assert saved_delivery.response_body == "server error"
    assert saved_delivery.latency_ms is not None


def patch_http_client(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    text: str,
    posted: dict[str, Any] | None = None,
) -> None:
    class FakeResponse:
        def __init__(self) -> None:
            self.status_code = status_code
            self.text = text

    class FakeAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(
            self,
            url: str,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> FakeResponse:
            if posted is not None:
                posted.update({"url": url, "json": json, "headers": headers})
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
