import uuid
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict


class EndpointCreate(BaseModel):
    url: AnyHttpUrl
    event_types: list[str]


class EndpointCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    event_types: list[str]
    is_active: bool
    created_at: datetime
