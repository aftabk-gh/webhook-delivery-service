import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.exceptions import BadRequestError

MAX_EVENT_PAYLOAD_BYTES = 256 * 1024


class EventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=255)
    payload: dict[str, Any]
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)


class EventCreateResponse(BaseModel):
    id: uuid.UUID


class EventIngestResponse(BaseModel):
    id: uuid.UUID
    created: bool


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    idempotency_key: str | None
    received_at: datetime


def validate_event_create_payload(payload: Any) -> EventCreate:
    try:
        event_in = EventCreate.model_validate(payload)
    except ValidationError as exc:
        raise BadRequestError(
            "Invalid event payload.",
            code="INVALID_EVENT_PAYLOAD",
        ) from exc

    payload_size = len(
        json.dumps(
            event_in.payload,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )
    if payload_size > MAX_EVENT_PAYLOAD_BYTES:
        raise BadRequestError(
            "Event payload must be 256KB or smaller.",
            code="EVENT_PAYLOAD_TOO_LARGE",
        )

    return event_in
