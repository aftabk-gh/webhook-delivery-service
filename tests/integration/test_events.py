"""Integration tests for event ingestion flows."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.tenant import Tenant


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
