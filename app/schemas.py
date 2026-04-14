import uuid

from pydantic import BaseModel


class TenantCreate(BaseModel):
    name: str


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
