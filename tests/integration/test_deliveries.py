"""Integration tests for Celery delivery behavior."""

from collections.abc import Generator
from typing import Any

import pytest
import requests
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.delivery import Delivery
from app.models.endpoint import Endpoint
from app.models.event import Event
from app.models.tenant import Tenant
from app.queries.delivery import get_pending_delivery_for_update
from app.services import delivery as delivery_service


class DeliveryTestSettings(BaseSettings):
    """Settings used by the sync worker integration tests."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    test_sync_database_url: str | None = None


@pytest.fixture
def sync_test_engine() -> Generator[Engine]:
    database_url = DeliveryTestSettings().test_sync_database_url
    if not database_url:
        pytest.skip(
            "TEST_SYNC_DATABASE_URL is required for sync DB-backed integration tests."
        )

    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def sync_db_session(sync_test_engine: Engine) -> Generator[Session]:
    Base.metadata.drop_all(bind=sync_test_engine)
    Base.metadata.create_all(bind=sync_test_engine)

    session_factory = sessionmaker(bind=sync_test_engine, expire_on_commit=False)
    session = session_factory()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=sync_test_engine)


@pytest.fixture
def patch_worker_session_factory(
    monkeypatch: pytest.MonkeyPatch,
    sync_test_engine: Engine,
) -> None:
    session_factory = sessionmaker(bind=sync_test_engine, expire_on_commit=False)
    monkeypatch.setattr(delivery_service, "SessionLocal", session_factory)


def create_tenant_event_and_endpoints(
    db_session: Session,
) -> tuple[Tenant, Event, Endpoint, Endpoint, Endpoint, Endpoint]:
    tenant = Tenant(name="Acme")
    other_tenant = Tenant(name="Globex")
    db_session.add_all([tenant, other_tenant])
    db_session.flush()

    event = Event(
        tenant_id=tenant.id,
        event_type="order.created",
        payload={"order_id": "ord_123"},
        idempotency_key="evt_ord_123",
    )
    matching_endpoint = Endpoint(
        tenant_id=tenant.id,
        url="https://example.com/webhooks/matching",
        event_types=["order.created", "order.updated"],
        is_active=True,
    )
    inactive_endpoint = Endpoint(
        tenant_id=tenant.id,
        url="https://example.com/webhooks/inactive",
        event_types=["order.created"],
        is_active=False,
    )
    non_matching_endpoint = Endpoint(
        tenant_id=tenant.id,
        url="https://example.com/webhooks/non-matching",
        event_types=["invoice.paid"],
        is_active=True,
    )
    other_tenant_endpoint = Endpoint(
        tenant_id=other_tenant.id,
        url="https://example.com/webhooks/other-tenant",
        event_types=["order.created"],
        is_active=True,
    )
    db_session.add_all(
        [
            event,
            matching_endpoint,
            inactive_endpoint,
            non_matching_endpoint,
            other_tenant_endpoint,
        ]
    )
    db_session.commit()

    return (
        tenant,
        event,
        matching_endpoint,
        inactive_endpoint,
        non_matching_endpoint,
        other_tenant_endpoint,
    )


def test_fan_out_event_deliveries_creates_delivery_for_matching_endpoint(
    sync_db_session: Session,
    patch_worker_session_factory: None,
) -> None:
    tenant, event, matching_endpoint, *_ = create_tenant_event_and_endpoints(
        sync_db_session
    )
    dispatched_tasks: list[tuple[list[str], str]] = []

    def dispatch_delivery(*, args: list[str], queue: str) -> None:
        dispatched_tasks.append((args, queue))

    delivery_service.fan_out_event_deliveries(
        event_id=str(event.id),
        tenant_id=str(tenant.id),
        dispatch_delivery=dispatch_delivery,
    )

    delivery = sync_db_session.execute(
        select(Delivery).where(
            Delivery.tenant_id == tenant.id,
            Delivery.event_id == event.id,
        )
    ).scalar_one()

    assert delivery.endpoint_id == matching_endpoint.id
    assert delivery.status == "pending"
    assert dispatched_tasks == [([str(delivery.id), str(tenant.id)], "delivery")]


def test_fan_out_event_deliveries_ignores_non_matching_and_cross_tenant_endpoints(
    sync_db_session: Session,
    patch_worker_session_factory: None,
) -> None:
    tenant, event, matching_endpoint, *_ = create_tenant_event_and_endpoints(
        sync_db_session
    )

    delivery_service.fan_out_event_deliveries(
        event_id=str(event.id),
        tenant_id=str(tenant.id),
        dispatch_delivery=lambda **_: None,
    )

    deliveries = list(
        sync_db_session.execute(
            select(Delivery).where(
                Delivery.tenant_id == tenant.id,
                Delivery.event_id == event.id,
            )
        )
        .scalars()
        .all()
    )
    delivery_count = sync_db_session.scalar(select(func.count()).select_from(Delivery))

    assert delivery_count == 1
    assert [delivery.endpoint_id for delivery in deliveries] == [matching_endpoint.id]


def test_deliver_to_endpoint_once_marks_success_after_200_response(
    sync_db_session: Session,
    patch_worker_session_factory: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant, event, endpoint, *_ = create_tenant_event_and_endpoints(sync_db_session)
    delivery = Delivery(
        tenant_id=tenant.id,
        event_id=event.id,
        endpoint_id=endpoint.id,
        status="pending",
    )
    sync_db_session.add(delivery)
    sync_db_session.commit()
    delivery_id = delivery.id

    posted: dict[str, Any] = {}
    patch_http_client(monkeypatch, status_code=200, text="ok", posted=posted)

    delivery_service.deliver_to_endpoint_once(
        delivery_id=str(delivery_id),
        tenant_id=str(tenant.id),
    )

    sync_db_session.expire_all()
    saved_delivery = sync_db_session.get(Delivery, delivery_id)

    assert saved_delivery is not None
    assert saved_delivery.status == "success"
    assert saved_delivery.http_status_code == 200
    assert saved_delivery.response_body == "ok"
    assert saved_delivery.latency_ms is not None
    assert posted["url"] == endpoint.url
    assert posted["json"] == event.payload
    assert posted["headers"]["X-Webhook-Event-ID"] == str(event.id)
    assert posted["headers"]["X-Webhook-Event-Type"] == event.event_type


def test_deliver_to_endpoint_once_marks_failed_after_500_response(
    sync_db_session: Session,
    patch_worker_session_factory: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant, event, endpoint, *_ = create_tenant_event_and_endpoints(sync_db_session)
    delivery = Delivery(
        tenant_id=tenant.id,
        event_id=event.id,
        endpoint_id=endpoint.id,
        status="pending",
    )
    sync_db_session.add(delivery)
    sync_db_session.commit()
    delivery_id = delivery.id

    patch_http_client(monkeypatch, status_code=500, text="server error")

    delivery_service.deliver_to_endpoint_once(
        delivery_id=str(delivery_id),
        tenant_id=str(tenant.id),
    )

    sync_db_session.expire_all()
    saved_delivery = sync_db_session.get(Delivery, delivery_id)

    assert saved_delivery is not None
    assert saved_delivery.status == "failed"
    assert saved_delivery.http_status_code == 500
    assert saved_delivery.response_body == "server error"
    assert saved_delivery.latency_ms is not None


def test_deliver_to_endpoint_once_marks_failed_after_timeout(
    sync_db_session: Session,
    patch_worker_session_factory: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant, event, endpoint, *_ = create_tenant_event_and_endpoints(sync_db_session)
    delivery = Delivery(
        tenant_id=tenant.id,
        event_id=event.id,
        endpoint_id=endpoint.id,
        status="pending",
    )
    sync_db_session.add(delivery)
    sync_db_session.commit()
    delivery_id = delivery.id

    patch_http_client_exception(monkeypatch, requests.Timeout("request timed out"))

    delivery_service.deliver_to_endpoint_once(
        delivery_id=str(delivery_id),
        tenant_id=str(tenant.id),
    )

    sync_db_session.expire_all()
    saved_delivery = sync_db_session.get(Delivery, delivery_id)

    assert saved_delivery is not None
    assert saved_delivery.status == "failed"
    assert saved_delivery.http_status_code is None
    assert saved_delivery.response_body == "request timed out"
    assert saved_delivery.latency_ms is not None


def test_deliver_to_endpoint_once_marks_failed_after_connection_error(
    sync_db_session: Session,
    patch_worker_session_factory: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant, event, endpoint, *_ = create_tenant_event_and_endpoints(sync_db_session)
    delivery = Delivery(
        tenant_id=tenant.id,
        event_id=event.id,
        endpoint_id=endpoint.id,
        status="pending",
    )
    sync_db_session.add(delivery)
    sync_db_session.commit()
    delivery_id = delivery.id

    patch_http_client_exception(
        monkeypatch, requests.ConnectionError("connection failed")
    )

    delivery_service.deliver_to_endpoint_once(
        delivery_id=str(delivery_id),
        tenant_id=str(tenant.id),
    )

    sync_db_session.expire_all()
    saved_delivery = sync_db_session.get(Delivery, delivery_id)

    assert saved_delivery is not None
    assert saved_delivery.status == "failed"
    assert saved_delivery.http_status_code is None
    assert saved_delivery.response_body == "connection failed"
    assert saved_delivery.latency_ms is not None


def test_get_pending_delivery_for_update_skips_locked_delivery(
    sync_db_session: Session,
    sync_test_engine: Engine,
) -> None:
    tenant, event, endpoint, *_ = create_tenant_event_and_endpoints(sync_db_session)
    delivery = Delivery(
        tenant_id=tenant.id,
        event_id=event.id,
        endpoint_id=endpoint.id,
        status="pending",
    )
    sync_db_session.add(delivery)
    sync_db_session.commit()

    session_factory = sessionmaker(bind=sync_test_engine, expire_on_commit=False)
    first_worker_session = session_factory()
    second_worker_session = session_factory()

    try:
        first_worker_delivery = get_pending_delivery_for_update(
            session=first_worker_session,
            delivery_id=delivery.id,
            tenant_id=tenant.id,
        )
        second_worker_delivery = get_pending_delivery_for_update(
            session=second_worker_session,
            delivery_id=delivery.id,
            tenant_id=tenant.id,
        )

        assert first_worker_delivery is not None
        assert second_worker_delivery is None
    finally:
        first_worker_session.rollback()
        second_worker_session.rollback()
        first_worker_session.close()
        second_worker_session.close()


def patch_http_client(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    text: str,
    posted: dict[str, Any] | None = None,
) -> None:
    class FakeResponse:
        def __init__(self) -> None:
            self.status_code = status_code
            self.text = text

    class FakeClient:
        def __init__(self) -> None:
            self.timeout: float | None = None

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(
            self,
            url: str,
            json: dict[str, Any],
            headers: dict[str, str],
            timeout: float,
        ) -> FakeResponse:
            self.timeout = timeout
            if posted is not None:
                posted.update({"url": url, "json": json, "headers": headers})
            return FakeResponse()

    monkeypatch.setattr(requests, "Session", FakeClient)


def patch_http_client_exception(
    monkeypatch: pytest.MonkeyPatch,
    exception: requests.RequestException,
) -> None:
    class FakeClient:
        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(
            self,
            url: str,
            json: dict[str, Any],
            headers: dict[str, str],
            timeout: float,
        ) -> object:
            raise exception

    monkeypatch.setattr(requests, "Session", FakeClient)
