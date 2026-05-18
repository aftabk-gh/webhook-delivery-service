from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_tenant
from app.database import get_db
from app.models import Tenant
from app.schemas.event import (
    EventCreate,
    EventCreateResponse,
    validate_event_create_payload,
)
from app.services.event import ingest_event

router = APIRouter(prefix="/events", tags=["events"])


@router.post(
    "/",
    response_model=EventCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_event_route(
    payload: EventCreate,
    response: Response,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> EventCreateResponse:
    validated_payload = validate_event_create_payload(payload.model_dump())
    result = await ingest_event(session=db, tenant=tenant, event_in=validated_payload)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return EventCreateResponse(id=result.id)
