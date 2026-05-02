from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_tenant
from app.database import get_db
from app.models import Tenant
from app.schemas.tenant import (
    TenantCreate,
    TenantCreateResponse,
    TenantGetResponse,
)
from app.services.tenant import create_tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post(
    "/", response_model=TenantCreateResponse, status_code=status.HTTP_201_CREATED
)
async def create_tenant_route(
    payload: TenantCreate,
    db: AsyncSession = Depends(get_db),
) -> TenantCreateResponse:
    tenant = await create_tenant(session=db, tenant_in=payload)
    return TenantCreateResponse.model_validate(tenant)


@router.get("/me/", response_model=TenantGetResponse, status_code=status.HTTP_200_OK)
async def get_tenant_me(
    tenant: Tenant = Depends(get_current_tenant),
) -> TenantGetResponse:
    return TenantGetResponse.model_validate(tenant)
