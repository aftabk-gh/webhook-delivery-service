from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_tenant
from app.database import get_db
from app.models.tenant import Tenant
from app.schemas.endpoint import (
    EndpointCreate,
    EndpointCreateResponse,
    EndpointListResponse,
)
from app.services.endpoint import create_endpoint, list_endpoints

router = APIRouter(prefix="/endpoints", tags=["endpoints"])


@router.get(
    "/",
    response_model=list[EndpointListResponse],
    status_code=status.HTTP_200_OK,
)
async def list_endpoints_route(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[EndpointListResponse]:
    endpoints = await list_endpoints(session=db, tenant=tenant)
    return [EndpointListResponse.model_validate(endpoint) for endpoint in endpoints]


@router.post(
    "/",
    response_model=EndpointCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_endpoint_route(
    payload: EndpointCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> EndpointCreateResponse:
    endpoint = await create_endpoint(session=db, tenant=tenant, endpoint_in=payload)
    return EndpointCreateResponse.model_validate(endpoint)
