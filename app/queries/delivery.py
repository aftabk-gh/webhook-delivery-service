import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.delivery import Delivery
from app.models.endpoint import Endpoint
from app.models.event import Event
from app.models.tenant import Tenant


async def list_deliveries_by_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    status: str | None = None,
    endpoint_id: uuid.UUID | None = None,
) -> list[Delivery]:
    filters = [Delivery.tenant_id == tenant_id]
    if status is not None:
        filters.append(Delivery.status == status)
    if endpoint_id is not None:
        filters.append(Delivery.endpoint_id == endpoint_id)

    result = await session.execute(
        select(Delivery).where(*filters).order_by(Delivery.created_at.desc())
    )
    return list(result.scalars().all())


def get_event_for_tenant(
    session: Session,
    event_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Event | None:
    result = session.execute(
        select(Event).where(
            Event.id == event_id,
            Event.tenant_id == tenant_id,
        )
    )
    # Run EXPLAIN ANALYZE on this query after seeding test data to confirm index scan.
    return result.scalar_one_or_none()


def get_tenant_by_id(
    session: Session,
    tenant_id: uuid.UUID,
) -> Tenant | None:
    result = session.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


def list_active_matching_endpoints_for_tenant(
    session: Session,
    tenant_id: uuid.UUID,
    event_type: str,
) -> list[Endpoint]:
    result = session.execute(
        select(Endpoint).where(
            Endpoint.tenant_id == tenant_id,
            Endpoint.is_active.is_(True),
            Endpoint.event_types.contains([event_type]),
        )
    )
    # Run EXPLAIN ANALYZE on this query after seeding test data to confirm index scan.
    return list(result.scalars().all())


def add_delivery(
    session: Session,
    event_id: uuid.UUID,
    endpoint_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Delivery:
    delivery = Delivery(
        event_id=event_id,
        endpoint_id=endpoint_id,
        tenant_id=tenant_id,
    )
    session.add(delivery)
    return delivery


def get_pending_delivery_for_update(
    session: Session,
    delivery_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Delivery | None:
    now = datetime.now(UTC).replace(tzinfo=None)
    result = session.execute(
        select(Delivery)
        .where(
            Delivery.id == delivery_id,
            Delivery.tenant_id == tenant_id,
            Delivery.status == "pending",
            or_(
                Delivery.next_retry_at.is_(None),
                Delivery.next_retry_at <= now,
            ),
        )
        .with_for_update(skip_locked=True)
    )
    # Run EXPLAIN ANALYZE on this query after seeding test data to confirm index scan.
    return result.scalar_one_or_none()


def list_due_pending_deliveries(
    session: Session,
    now: datetime,
    limit: int,
) -> list[Delivery]:
    # This is an intentional cross-tenant maintenance query.
    # The recovery poller re-enqueues due pending deliveries across all tenants.
    result = session.execute(
        select(Delivery)
        .where(
            Delivery.status == "pending",
            Delivery.next_retry_at.is_not(None),
            Delivery.next_retry_at <= now,
        )
        .order_by(Delivery.next_retry_at.asc())
        .limit(limit)
    )
    # Run EXPLAIN ANALYZE on this query after seeding test data to confirm index scan.
    return list(result.scalars().all())


def get_active_endpoint_for_tenant(
    session: Session,
    endpoint_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Endpoint | None:
    result = session.execute(
        select(Endpoint).where(
            Endpoint.id == endpoint_id,
            Endpoint.is_active.is_(True),
            Endpoint.tenant_id == tenant_id,
        )
    )
    # Run EXPLAIN ANALYZE on this query after seeding test data to confirm index scan.
    return result.scalar_one_or_none()
