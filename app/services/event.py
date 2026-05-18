from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Tenant
from app.queries.event import insert_event_idempotently_for_tenant
from app.schemas.event import EventCreate, EventIngestResponse

logger = get_logger(__name__)


async def ingest_event(
    session: AsyncSession,
    tenant: Tenant,
    event_in: EventCreate,
) -> EventIngestResponse:
    try:
        result = await insert_event_idempotently_for_tenant(
            session=session,
            tenant_id=tenant.id,
            event_in=event_in,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    if result.created:
        logger.info(
            "event_ingested",
            tenant_id=str(tenant.id),
            event_id=str(result.event_id),
        )
    else:
        logger.info(
            "duplicate_event_ignored",
            tenant_id=str(tenant.id),
            event_id=str(result.event_id),
        )

    return EventIngestResponse(id=result.event_id, created=result.created)
