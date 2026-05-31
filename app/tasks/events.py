import asyncio

from app.core.logging import configure_logging, get_logger
from app.services.delivery import deliver_to_endpoint_once, fan_out_event_deliveries
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
    asyncio.run(
        fan_out_event_deliveries(
            event_id=event_id,
            tenant_id=tenant_id,
            dispatch_delivery=deliver_to_endpoint.apply_async,
        )
    )


@celery_app.task(name="events.deliver_to_endpoint", queue="delivery", acks_late=True)  # type: ignore[untyped-decorator]
def deliver_to_endpoint(delivery_id: str, tenant_id: str) -> None:
    logger.info(
        "endpoint_delivery_task_received",
        tenant_id=tenant_id,
        delivery_id=delivery_id,
    )

    asyncio.run(deliver_to_endpoint_once(delivery_id=delivery_id, tenant_id=tenant_id))
