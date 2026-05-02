import uuid

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
