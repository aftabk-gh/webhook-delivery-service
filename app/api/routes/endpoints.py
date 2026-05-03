import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_tenant
from app.database import get_db
from app.models.tenant import Tenant
from app.schemas.endpoint import (
    EndpointCreate,
    EndpointCreateResponse,
    EndpointListResponse,
    EndpointUpdate,
    EndpointUpdateResponse,
)
from app.services.endpoint import (
    create_endpoint,
    delete_endpoint,
    list_endpoints,
    update_endpoint,
)

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


@router.patch(
    "/{endpoint_id}/",
    response_model=EndpointUpdateResponse,
    status_code=status.HTTP_200_OK,
)
async def update_endpoint_route(
    endpoint_id: uuid.UUID,
    payload: EndpointUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> EndpointUpdateResponse:
    endpoint = await update_endpoint(
        session=db,
        tenant=tenant,
        endpoint_id=endpoint_id,
        endpoint_in=payload,
    )
    return EndpointUpdateResponse.model_validate(endpoint)


@router.delete(
    "/{endpoint_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_endpoint_route(
    endpoint_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await delete_endpoint(
        session=db,
        tenant=tenant,
        endpoint_id=endpoint_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
