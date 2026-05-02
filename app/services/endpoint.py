from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.core.logging import get_logger
from app.models.endpoint import Endpoint
from app.models.tenant import Tenant
from app.queries.endpoint import add_endpoint, build_endpoint
from app.schemas.endpoint import EndpointCreate

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
