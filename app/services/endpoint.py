import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.endpoint import Endpoint
from app.models.tenant import Tenant
from app.queries.endpoint import (
    add_endpoint,
    build_endpoint,
    get_active_endpoint_by_id_for_tenant,
    list_active_endpoints_by_tenant,
)
from app.schemas.endpoint import EndpointCreate, EndpointUpdate

logger = get_logger(__name__)


async def create_endpoint(
    session: AsyncSession,
    tenant: Tenant,
    endpoint_in: EndpointCreate,
) -> Endpoint:
    endpoint = build_endpoint(
        tenant_id=tenant.id,
        url=str(endpoint_in.url),
        event_types=endpoint_in.event_types,
    )
    add_endpoint(session, endpoint)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "Endpoint could not be created.",
            code="ENDPOINT_CONFLICT",
        ) from exc

    await session.refresh(endpoint)
    logger.info(
        "endpoint_created",
        tenant_id=str(tenant.id),
        endpoint_id=str(endpoint.id),
    )
    return endpoint


async def list_endpoints(
    session: AsyncSession,
    tenant: Tenant,
) -> list[Endpoint]:
    return await list_active_endpoints_by_tenant(
        session=session,
        tenant_id=tenant.id,
    )


async def update_endpoint(
    session: AsyncSession,
    tenant: Tenant,
    endpoint_id: uuid.UUID,
    endpoint_in: EndpointUpdate,
) -> Endpoint:
    endpoint = await get_active_endpoint_by_id_for_tenant(
        session=session,
        tenant_id=tenant.id,
        endpoint_id=endpoint_id,
    )
    if endpoint is None:
        raise NotFoundError("Endpoint not found.", code="ENDPOINT_NOT_FOUND")

    if endpoint_in.url is not None:
        endpoint.url = str(endpoint_in.url)
    if endpoint_in.event_types is not None:
        endpoint.event_types = endpoint_in.event_types

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "Endpoint could not be updated.",
            code="ENDPOINT_CONFLICT",
        ) from exc

    await session.refresh(endpoint)
    logger.info(
        "endpoint_updated",
        tenant_id=str(tenant.id),
        endpoint_id=str(endpoint.id),
    )
    return endpoint


async def delete_endpoint(
    session: AsyncSession,
    tenant: Tenant,
    endpoint_id: uuid.UUID,
) -> None:
    endpoint = await get_active_endpoint_by_id_for_tenant(
        session=session,
        tenant_id=tenant.id,
        endpoint_id=endpoint_id,
    )
    if endpoint is None:
        raise NotFoundError("Endpoint not found.", code="ENDPOINT_NOT_FOUND")

    endpoint.is_active = False
    await session.commit()
    logger.info(
        "endpoint_deleted",
        tenant_id=str(tenant.id),
        endpoint_id=str(endpoint.id),
    )
