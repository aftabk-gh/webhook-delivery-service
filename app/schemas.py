import uuid

from pydantic import BaseModel


class TenantCreate(BaseModel):
    name: str


class TenantCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    api_key: str


class TenantGetResponse(BaseModel):
    id: uuid.UUID
    name: str
    signing_secret: str
