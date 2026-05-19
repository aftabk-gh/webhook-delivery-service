"""Integration tests for event ingestion flows."""

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.event import Event
from app.models.tenant import Tenant
from app.schemas.event import EventCreate
from app.services import event as event_service
from app.tasks.events import deliver_event


def patch_event_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[list[str], str]]:
    dispatched_tasks: list[tuple[list[str], str]] = []

    def fake_apply_async(*, args: list[str], queue: str) -> None:
        dispatched_tasks.append((args, queue))

    monkeypatch.setattr(deliver_event, "apply_async", fake_apply_async)
    return dispatched_tasks


async def test_create_event_returns_202_persists_event_and_dispatches_task(
    db_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched_tasks = patch_event_dispatch(monkeypatch)
    tenant_response = await db_client.post("/tenants/", json={"name": "Acme"})
    api_key = tenant_response.json()["api_key"]
    tenant_id = uuid.UUID(tenant_response.json()["id"])

    response = await db_client.post(
        "/events/",
        json={
            "event_type": "order.created",
            "payload": {"order_id": "ord_123"},
            "idempotency_key": "evt_ord_123",
        },
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 202
    event_id = uuid.UUID(response.json()["id"])
    saved_event = await db_session.get(Event, event_id)

    assert saved_event is not None
    assert saved_event.tenant_id == tenant_id
    assert saved_event.event_type == "order.created"
    assert saved_event.payload == {"order_id": "ord_123"}
    assert dispatched_tasks == [
        ([str(event_id), str(tenant_id), "evt_ord_123"], "default")
    ]


async def test_create_event_duplicate_idempotency_key_returns_200_without_dispatch(
    db_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched_tasks = patch_event_dispatch(monkeypatch)
    tenant_response = await db_client.post("/tenants/", json={"name": "Acme"})
    api_key = tenant_response.json()["api_key"]

    first_response = await db_client.post(
        "/events/",
        json={
            "event_type": "order.created",
            "payload": {"order_id": "ord_123"},
            "idempotency_key": "evt_duplicate",
        },
        headers={"X-API-Key": api_key},
    )
    second_response = await db_client.post(
        "/events/",
        json={
            "event_type": "order.created",
            "payload": {"order_id": "ord_123"},
            "idempotency_key": "evt_duplicate",
        },
        headers={"X-API-Key": api_key},
    )

    count_statement = (
        select(func.count())
        .select_from(Event)
        .where(Event.idempotency_key == "evt_duplicate")
    )
    event_count = await db_session.scalar(count_statement)

    assert first_response.status_code == 202
    assert second_response.status_code == 200
    assert second_response.json()["id"] == first_response.json()["id"]
    assert event_count == 1
    assert len(dispatched_tasks) == 1


async def test_create_event_same_idempotency_key_is_scoped_per_tenant(
    db_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched_tasks = patch_event_dispatch(monkeypatch)
    first_tenant_response = await db_client.post("/tenants/", json={"name": "Acme"})
    second_tenant_response = await db_client.post("/tenants/", json={"name": "Globex"})

    first_response = await db_client.post(
        "/events/",
        json={
            "event_type": "order.created",
            "payload": {"order_id": "ord_123"},
            "idempotency_key": "evt_shared",
        },
        headers={"X-API-Key": first_tenant_response.json()["api_key"]},
    )
    second_response = await db_client.post(
        "/events/",
        json={
            "event_type": "order.created",
            "payload": {"order_id": "ord_123"},
            "idempotency_key": "evt_shared",
        },
        headers={"X-API-Key": second_tenant_response.json()["api_key"]},
    )

    count_statement = (
        select(func.count())
        .select_from(Event)
        .where(Event.idempotency_key == "evt_shared")
    )
    event_count = await db_session.scalar(count_statement)

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert first_response.json()["id"] != second_response.json()["id"]
    assert event_count == 2
    assert len(dispatched_tasks) == 2


async def test_concurrent_duplicate_idempotency_key_creates_one_event_and_one_task(
    db_session: AsyncSession,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched_tasks = patch_event_dispatch(monkeypatch)
    tenant = Tenant(name="Acme")
    db_session.add(tenant)
    await db_session.commit()

    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    event_in = EventCreate(
        event_type="order.created",
        payload={"order_id": "ord_123"},
        idempotency_key="evt_concurrent",
    )

    async def ingest_with_new_session() -> dict[str, Any]:
        async with session_factory() as session:
            result = await event_service.ingest_event(
                session=session,
                tenant=tenant,
                event_in=event_in,
            )
            return result.model_dump()

    first_result, second_result = await asyncio.gather(
        ingest_with_new_session(),
        ingest_with_new_session(),
    )

    count_statement = (
        select(func.count())
        .select_from(Event)
        .where(
            Event.tenant_id == tenant.id,
            Event.idempotency_key == "evt_concurrent",
        )
    )
    event_count = await db_session.scalar(count_statement)
    result_ids = {first_result["id"], second_result["id"]}

    assert event_count == 1
    assert len(result_ids) == 1
    assert {first_result["created"], second_result["created"]} == {True, False}
    assert len(dispatched_tasks) == 1


async def test_event_model_persists_event_payload(
    db_session: AsyncSession,
) -> None:
    tenant = Tenant(name="Acme")
    db_session.add(tenant)
    await db_session.flush()

    event = Event(
        tenant_id=tenant.id,
        event_type="order.created",
        payload={"order_id": "ord_123", "total": 4999},
        idempotency_key="evt_ord_123",
    )
    db_session.add(event)
    await db_session.commit()

    saved_event = await db_session.get(Event, event.id)

    assert saved_event is not None
    assert saved_event.tenant_id == tenant.id
    assert saved_event.event_type == "order.created"
    assert saved_event.payload == {"order_id": "ord_123", "total": 4999}
    assert saved_event.idempotency_key == "evt_ord_123"
    assert saved_event.received_at is not None


async def test_event_model_rejects_duplicate_idempotency_key_for_same_tenant(
    db_session: AsyncSession,
) -> None:
    tenant = Tenant(name="Acme")
    db_session.add(tenant)
    await db_session.flush()

    db_session.add_all(
        [
            Event(
                tenant_id=tenant.id,
                event_type="order.created",
                payload={"order_id": "ord_123"},
                idempotency_key="evt_ord_123",
            ),
            Event(
                tenant_id=tenant.id,
                event_type="order.updated",
                payload={"order_id": "ord_123"},
                idempotency_key="evt_ord_123",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_event_model_allows_same_idempotency_key_for_different_tenants(
    db_session: AsyncSession,
) -> None:
    first_tenant = Tenant(name="Acme")
    second_tenant = Tenant(name="Globex")
    db_session.add_all([first_tenant, second_tenant])
    await db_session.flush()

    db_session.add_all(
        [
            Event(
                tenant_id=first_tenant.id,
                event_type="order.created",
                payload={"order_id": "ord_123"},
                idempotency_key="evt_ord_123",
            ),
            Event(
                tenant_id=second_tenant.id,
                event_type="order.created",
                payload={"order_id": "ord_123"},
                idempotency_key="evt_ord_123",
            ),
        ]
    )

    await db_session.commit()
