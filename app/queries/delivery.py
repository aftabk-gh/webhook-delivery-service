import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.delivery import Delivery
from app.models.endpoint import Endpoint
from app.models.event import Event


async def get_event_for_tenant(
    session: AsyncSession,
    event_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Event | None:
    result = await session.execute(
        select(Event).where(
            Event.id == event_id,
            Event.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def list_active_matching_endpoints_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    event_type: str,
) -> list[Endpoint]:
    result = await session.execute(
        select(Endpoint).where(
            Endpoint.tenant_id == tenant_id,
            Endpoint.is_active.is_(True),
            Endpoint.event_types.contains([event_type]),
        )
    )
    return list(result.scalars().all())


def add_delivery(
    session: AsyncSession,
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


async def get_pending_delivery_for_update(
    session: AsyncSession,
    delivery_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Delivery | None:
    result = await session.execute(
        select(Delivery)
        .where(
            Delivery.id == delivery_id,
            Delivery.tenant_id == tenant_id,
            Delivery.status == "pending",
        )
        .with_for_update(skip_locked=True)
    )
    return result.scalar_one_or_none()


async def get_active_endpoint_for_tenant(
    session: AsyncSession,
    endpoint_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Endpoint | None:
    result = await session.execute(
        select(Endpoint).where(
            Endpoint.id == endpoint_id,
            Endpoint.is_active.is_(True),
            Endpoint.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()
