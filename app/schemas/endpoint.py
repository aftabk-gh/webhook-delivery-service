import uuid
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, model_validator


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


class EndpointListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    event_types: list[str]
    is_active: bool
    created_at: datetime


class EndpointUpdate(BaseModel):
    url: AnyHttpUrl | None = None
    event_types: list[str] | None = None

    @model_validator(mode="after")
    def validate_update_payload(self) -> "EndpointUpdate":
        if self.url is None and self.event_types is None:
            raise ValueError("At least one field must be provided.")
        return self


class EndpointUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    event_types: list[str]
    is_active: bool
    created_at: datetime
