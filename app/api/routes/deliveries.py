import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_tenant
from app.database import get_db
from app.models.tenant import Tenant
from app.schemas.delivery import DeliveryListResponse
from app.services.delivery import list_delivery_logs

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.get(
    "/",
    response_model=list[DeliveryListResponse],
    status_code=status.HTTP_200_OK,
)
async def list_deliveries_route(
    delivery_status: str | None = Query(default=None, alias="status"),
    endpoint_id: uuid.UUID | None = None,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[DeliveryListResponse]:
    deliveries = await list_delivery_logs(
        session=db,
        tenant=tenant,
        status=delivery_status,
        endpoint_id=endpoint_id,
    )
    return [DeliveryListResponse.model_validate(delivery) for delivery in deliveries]
