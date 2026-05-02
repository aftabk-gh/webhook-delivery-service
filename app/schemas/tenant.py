import uuid

from pydantic import BaseModel, ConfigDict


class TenantCreate(BaseModel):
    name: str


class TenantCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    api_key: str


class TenantGetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    signing_secret: str
