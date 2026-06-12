import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

from app.core.logging import get_logger
from app.database import SessionLocal
from app.models.delivery import Delivery
from app.models.endpoint import Endpoint
from app.models.event import Event
from app.queries.delivery import (
    add_delivery,
    get_active_endpoint_for_tenant,
    get_event_for_tenant,
    get_pending_delivery_for_update,
    list_active_matching_endpoints_for_tenant,
    list_due_pending_deliveries,
)

logger = get_logger(__name__)

TaskDispatcher = Callable[..., Any]
RETRY_DELAYS_SECONDS = [30, 120, 600]


def fan_out_event_deliveries(
    event_id: str,
    tenant_id: str,
    dispatch_delivery: TaskDispatcher,
) -> None:
    parsed_event_id = uuid.UUID(event_id)
    parsed_tenant_id = uuid.UUID(tenant_id)

    with SessionLocal() as session:
        event = get_event_for_tenant(
            session=session,
            event_id=parsed_event_id,
            tenant_id=parsed_tenant_id,
        )
        if event is None:
            logger.warning(
                "event_delivery_task_event_not_found",
                tenant_id=tenant_id,
                event_id=event_id,
            )
            return

        endpoints = list_active_matching_endpoints_for_tenant(
            session=session,
            tenant_id=parsed_tenant_id,
            event_type=event.event_type,
        )

        deliveries: list[Delivery] = []
        for endpoint in endpoints:
            delivery = add_delivery(
                session=session,
                event_id=parsed_event_id,
                endpoint_id=endpoint.id,
                tenant_id=parsed_tenant_id,
            )
            deliveries.append(delivery)

        session.commit()

    for delivery in deliveries:
        dispatch_delivery(args=[str(delivery.id), tenant_id], queue="delivery")


def deliver_to_endpoint_once(
    delivery_id: str,
    tenant_id: str,
    dispatch_delivery: TaskDispatcher | None = None,
) -> None:
    if dispatch_delivery is None:
        from app.tasks.events import deliver_to_endpoint

        dispatch_delivery = deliver_to_endpoint.apply_async

    parsed_delivery_id = uuid.UUID(delivery_id)
    parsed_tenant_id = uuid.UUID(tenant_id)

    with SessionLocal() as session:
        delivery = get_pending_delivery_for_update(
            session=session,
            delivery_id=parsed_delivery_id,
            tenant_id=parsed_tenant_id,
        )
        if delivery is None:
            logger.info(
                "endpoint_delivery_noop",
                tenant_id=tenant_id,
                delivery_id=delivery_id,
            )
            return

        endpoint = get_active_endpoint_for_tenant(
            session=session,
            endpoint_id=delivery.endpoint_id,
            tenant_id=parsed_tenant_id,
        )
        event = get_event_for_tenant(
            session=session,
            event_id=delivery.event_id,
            tenant_id=parsed_tenant_id,
        )
        if endpoint is None or event is None:
            delivery.status = "failed"
            delivery.response_body = "Endpoint or event not found"
            session.commit()
            logger.warning(
                "endpoint_delivery_missing_related_record",
                tenant_id=tenant_id,
                delivery_id=delivery_id,
                endpoint_id=str(delivery.endpoint_id),
                event_id=str(delivery.event_id),
            )
            return

        _post_and_record_delivery(
            delivery=delivery,
            endpoint=endpoint,
            event=event,
            tenant_id=tenant_id,
            delivery_id=delivery_id,
            dispatch_delivery=dispatch_delivery,
        )
        session.commit()


def _post_and_record_delivery(
    delivery: Delivery,
    endpoint: Endpoint,
    event: Event,
    tenant_id: str,
    delivery_id: str,
    dispatch_delivery: TaskDispatcher,
) -> None:
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event-ID": str(event.id),
        "X-Webhook-Event-Type": event.event_type,
    }
    started_at = time.perf_counter()
    delivery.attempt_number += 1

    try:
        with requests.Session() as client:
            response = client.post(
                endpoint.url,
                json=event.payload,
                headers=headers,
                timeout=10.0,
            )

        delivery.http_status_code = response.status_code
        delivery.response_body = response.text[:500]
        delivery.status = "success" if 200 <= response.status_code <= 299 else "failed"
    except requests.RequestException as exc:
        delivery.status = "failed"
        delivery.http_status_code = None
        delivery.response_body = str(exc)[:500]
        logger.warning(
            "endpoint_delivery_http_error",
            tenant_id=tenant_id,
            delivery_id=delivery_id,
            endpoint_id=str(endpoint.id),
            event_id=str(event.id),
            error=str(exc),
        )

    delivery.latency_ms = int((time.perf_counter() - started_at) * 1000)
    if delivery.status == "failed":
        retry_index = delivery.attempt_number - 1
        if retry_index < len(RETRY_DELAYS_SECONDS):
            delay = RETRY_DELAYS_SECONDS[retry_index]
            delivery.status = "pending"
            delivery.next_retry_at = _utcnow() + timedelta(seconds=delay)
            dispatch_delivery(
                args=[str(delivery.id), tenant_id],
                queue="delivery",
                countdown=delay,
            )
            logger.info(
                "retry_scheduled",
                tenant_id=tenant_id,
                delivery_id=delivery_id,
                endpoint_id=str(endpoint.id),
                event_id=str(event.id),
                attempt_number=delivery.attempt_number,
                next_retry_at=delivery.next_retry_at.isoformat(),
            )
        else:
            delivery.status = "exhausted"
            delivery.next_retry_at = None
    else:
        delivery.next_retry_at = None

    logger.info(
        "endpoint_delivery_attempted",
        tenant_id=tenant_id,
        delivery_id=delivery_id,
        endpoint_id=str(endpoint.id),
        event_id=str(event.id),
        http_status_code=delivery.http_status_code,
        latency_ms=delivery.latency_ms,
        status=delivery.status,
        attempt_number=delivery.attempt_number,
    )


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def send_stuck_deliveries(
    dispatch_delivery: TaskDispatcher | None = None,
    batch_size: int = 1000,
) -> int:
    if dispatch_delivery is None:
        from app.tasks.events import deliver_to_endpoint

        dispatch_delivery = deliver_to_endpoint.apply_async

    with SessionLocal() as session:
        stuck_deliveries = list_due_pending_deliveries(
            session=session,
            now=_utcnow(),
            limit=batch_size,
        )

        for delivery in stuck_deliveries:
            dispatch_delivery(
                args=[str(delivery.id), str(delivery.tenant_id)],
                queue="delivery",
            )
            logger.info(
                "stuck_delivery_requeued",
                tenant_id=str(delivery.tenant_id),
                delivery_id=str(delivery.id),
            )

    return len(stuck_deliveries)
