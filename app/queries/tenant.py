from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant


def build_tenant(name: str) -> Tenant:
    return Tenant(name=name)


def add_tenant(session: AsyncSession, tenant: Tenant) -> None:
    session.add(tenant)


async def get_tenant_by_api_key(
    session: AsyncSession,
    api_key: str,
) -> Tenant | None:
    result = await session.execute(select(Tenant).where(Tenant.api_key == api_key))
    return result.scalar_one_or_none()
