from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.database import get_db
from app.models import Tenant
from app.services.tenant import authenticate_tenant


async def get_current_tenant(
    api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    if api_key is None:
        raise AuthenticationError("Missing API key.", code="AUTHENTICATION_FAILED")

    tenant = await authenticate_tenant(session=db, api_key=api_key)
    if tenant is None:
        raise AuthenticationError("Invalid API key.", code="AUTHENTICATION_FAILED")
    return tenant
