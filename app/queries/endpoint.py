import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.endpoint import Endpoint


def build_endpoint(
    tenant_id: uuid.UUID,
    url: str,
    event_types: list[str],
) -> Endpoint:
    return Endpoint(
        tenant_id=tenant_id,
        url=url,
        event_types=event_types,
    )


def add_endpoint(session: AsyncSession, endpoint: Endpoint) -> None:
    session.add(endpoint)


async def list_active_endpoints_by_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> list[Endpoint]:
    result = await session.execute(
        select(Endpoint)
        .where(
            Endpoint.tenant_id == tenant_id,
            Endpoint.is_active.is_(True),
        )
        .order_by(Endpoint.created_at.asc())
    )
    # Run EXPLAIN ANALYZE on this query after seeding test data to confirm index scan.
    return list(result.scalars().all())
