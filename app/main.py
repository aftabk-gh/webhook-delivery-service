from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Tenant
from app.redis import redis_client, verify_redis
from app.schemas import TenantCreate, TenantResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await verify_redis()
    yield
    await redis_client.aclose()


app = FastAPI(lifespan=lifespan)


class HealthResponse(BaseModel):
    status: str
    app_name: str
    redis: str


@app.get("/ping", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check() -> HealthResponse:
    await redis_client.ping()  # type: ignore[misc]
    return HealthResponse(status="ok", app_name=settings.app_name, redis="ok")


@app.post("/tenant", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant: TenantCreate, db: AsyncSession = Depends(get_db)
) -> TenantResponse:
    db_tenant = Tenant(name=tenant.name)
    db.add(db_tenant)
    await db.flush()
    await db.refresh(db_tenant)
    return TenantResponse(id=db_tenant.id, name=db_tenant.name)
