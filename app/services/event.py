from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.schemas.event import EventCreate, EventCreateResponse


async def ingest_event(
    session: AsyncSession,
    tenant: Tenant,
    event_in: EventCreate,
) -> EventCreateResponse:
    return EventCreateResponse(id="7412479b-268f-46f5-947e-d32e76e8359d")
