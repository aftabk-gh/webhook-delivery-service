from app.core.logging import configure_logging, get_logger
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
