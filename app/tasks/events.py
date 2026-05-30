import asyncio
import uuid

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.database import AsyncSessionLocal
from app.models.delivery import Delivery
from app.models.endpoint import Endpoint
from app.models.event import Event
from app.tasks.worker import celery_app

configure_logging()
logger = get_logger(__name__)


@celery_app.task(name="events.deliver_event", queue="default", acks_late=True)  # type: ignore[untyped-decorator]
def deliver_event(
    event_id: str,
    tenant_id: str,
    idempotency_key: str | None,
) -> None:
    logger.info(
        "event_delivery_task_received",
        tenant_id=tenant_id,
        event_id=event_id,
        idempotency_key=idempotency_key,
    )
    asyncio.run(_deliver_event(event_id=event_id, tenant_id=tenant_id))


@celery_app.task(name="events.deliver_to_endpoint", queue="delivery", acks_late=True)  # type: ignore[untyped-decorator]
def deliver_to_endpoint(delivery_id: str) -> None:
    logger.info(
        "endpoint_delivery_task_received",
        tenant_id="unknown",
        delivery_id=delivery_id,
    )


async def _deliver_event(event_id: str, tenant_id: str) -> None:
    parsed_event_id = uuid.UUID(event_id)
    parsed_tenant_id = uuid.UUID(tenant_id)

    async with AsyncSessionLocal() as session:
        event_result = await session.execute(
            select(Event).where(
                Event.id == parsed_event_id,
                Event.tenant_id == parsed_tenant_id,
            )
        )
        event: Event | None = event_result.scalar_one_or_none()
        if event is None:
            logger.warning(
                "event_delivery_task_event_not_found",
                tenant_id=tenant_id,
                event_id=event_id,
            )
            return

        endpoints_result = await session.execute(
            select(Endpoint).where(
                Endpoint.tenant_id == parsed_tenant_id,
                Endpoint.is_active.is_(True),
                Endpoint.event_types.contains([event.event_type]),
            )
        )
        endpoints: list[Endpoint] = list(endpoints_result.scalars().all())

        deliveries: list[Delivery] = []
        for endpoint in endpoints:
            delivery = Delivery(
                event_id=parsed_event_id,
                endpoint_id=endpoint.id,
                tenant_id=parsed_tenant_id,
            )
            session.add(delivery)
            deliveries.append(delivery)

        await session.commit()

    for delivery in deliveries:
        deliver_to_endpoint.apply_async(args=[str(delivery.id)], queue="delivery")
