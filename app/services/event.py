from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Tenant
from app.queries.event import insert_event_idempotently_for_tenant
from app.schemas.event import EventCreate, EventIngestResponse
from app.tasks.events import deliver_event

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
        deliver_event.apply_async(
            args=[str(result.event_id), str(tenant.id), event_in.idempotency_key],
            queue="default",
        )
        logger.info(
            "event_ingested",
            tenant_id=str(tenant.id),
            event_id=str(result.event_id),
            idempotency_key=event_in.idempotency_key,
        )
    else:
        logger.info(
            "duplicate_event_ignored",
            tenant_id=str(tenant.id),
            event_id=str(result.event_id),
            idempotency_key=event_in.idempotency_key,
        )

    return EventIngestResponse(id=result.event_id, created=result.created)
