import uuid
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.event import EventCreate


@dataclass(frozen=True, slots=True)
class EventInsertResult:
    event_id: uuid.UUID
    created: bool


async def insert_event_idempotently_for_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    event_in: EventCreate,
) -> EventInsertResult:
    event_id = uuid.uuid4()

    insert_statement = text(
        """
        INSERT INTO event (
            id,
            tenant_id,
            event_type,
            payload,
            idempotency_key,
            received_at
        )
        VALUES (
            :id,
            :tenant_id,
            :event_type,
            :payload,
            :idempotency_key,
            now()
        )
        RETURNING id
        """
    ).bindparams(
        bindparam("id", type_=UUID(as_uuid=True)),
        bindparam("tenant_id", type_=UUID(as_uuid=True)),
        bindparam("payload", type_=JSONB),
    )

    params = {
        "id": event_id,
        "tenant_id": tenant_id,
        "event_type": event_in.event_type,
        "payload": event_in.payload,
        "idempotency_key": event_in.idempotency_key,
    }

    if event_in.idempotency_key is None:
        inserted_id = (await session.execute(insert_statement, params)).scalar_one()
        return EventInsertResult(event_id=inserted_id, created=True)

    idempotent_insert_statement = text(
        """
        INSERT INTO event (
            id,
            tenant_id,
            event_type,
            payload,
            idempotency_key,
            received_at
        )
        VALUES (
            :id,
            :tenant_id,
            :event_type,
            :payload,
            :idempotency_key,
            now()
        )
        ON CONFLICT (tenant_id, idempotency_key)
        DO NOTHING
        RETURNING id
        """
    ).bindparams(
        bindparam("id", type_=UUID(as_uuid=True)),
        bindparam("tenant_id", type_=UUID(as_uuid=True)),
        bindparam("payload", type_=JSONB),
    )

    inserted_id = (
        await session.execute(idempotent_insert_statement, params)
    ).scalar_one_or_none()
    if inserted_id is not None:
        return EventInsertResult(event_id=inserted_id, created=True)

    existing_event_statement = text(
        """
        SELECT id
        FROM event
        WHERE tenant_id = :tenant_id
        AND idempotency_key = :idempotency_key
        """
    ).bindparams(
        bindparam("tenant_id", type_=UUID(as_uuid=True)),
    )
    # Run EXPLAIN ANALYZE on this query after seeding test data to confirm index scan.
    existing_id = (
        await session.execute(
            existing_event_statement,
            {
                "tenant_id": tenant_id,
                "idempotency_key": event_in.idempotency_key,
            },
        )
    ).scalar_one_or_none()

    if existing_id is None:
        raise RuntimeError("Idempotent event insert conflicted but no event was found.")

    return EventInsertResult(event_id=existing_id, created=False)
