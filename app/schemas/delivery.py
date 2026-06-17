import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeliveryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    endpoint_id: uuid.UUID
    status: str
    attempt_number: int
    next_retry_at: datetime | None
    http_status_code: int | None
    latency_ms: int | None
    created_at: datetime
    updated_at: datetime
