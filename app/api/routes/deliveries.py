import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_tenant
from app.database import get_db
from app.models.tenant import Tenant
from app.schemas.delivery import (
    DeliveryDetailResponse,
    DeliveryListPageResponse,
    DeliveryListResponse,
)
from app.services.delivery import get_delivery_log, list_delivery_logs

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.get(
    "/",
    response_model=DeliveryListPageResponse,
    status_code=status.HTTP_200_OK,
)
async def list_deliveries_route(
    delivery_status: str | None = Query(default=None, alias="status"),
    endpoint_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> DeliveryListPageResponse:
    page = await list_delivery_logs(
        session=db,
        tenant=tenant,
        status=delivery_status,
        endpoint_id=endpoint_id,
        cursor=cursor,
        limit=limit,
    )
    items = [DeliveryListResponse.model_validate(delivery) for delivery in page.items]
    return DeliveryListPageResponse(
        items=items,
        next_cursor=page.next_cursor,
    )


@router.get(
    "/{delivery_id}/",
    response_model=DeliveryDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_delivery_route(
    delivery_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> DeliveryDetailResponse:
    delivery = await get_delivery_log(
        session=db,
        tenant=tenant,
        delivery_id=delivery_id,
    )
    return DeliveryDetailResponse.model_validate(delivery)
