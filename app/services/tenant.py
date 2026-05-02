from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.core.logging import get_logger
from app.models import Tenant
from app.queries.tenant import (
    add_tenant,
    build_tenant,
    get_tenant_by_api_key,
)
from app.schemas.tenant import TenantCreate

logger = get_logger(__name__)


async def create_tenant(session: AsyncSession, tenant_in: TenantCreate) -> Tenant:
    tenant = build_tenant(name=tenant_in.name)
    add_tenant(session, tenant)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "Tenant could not be created.", code="TENANT_CONFLICT"
        ) from exc

    await session.refresh(tenant)
    logger.info(
        "tenant_created",
        tenant_id=str(tenant.id),
    )
    return tenant


async def authenticate_tenant(session: AsyncSession, api_key: str) -> Tenant | None:
    return await get_tenant_by_api_key(session=session, api_key=api_key)
