from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Tenant
from app.redis import redis_client, verify_redis
from app.schemas import TenantCreate, TenantCreateResponse, TenantGetResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        await verify_redis()
    except RedisError as e:
        print("Redis unavailable on startup: %s", e)
    yield
    await redis_client.aclose()


app = FastAPI(lifespan=lifespan)


class HealthResponse(BaseModel):
    status: str
    app_name: str
    redis: str


@app.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check() -> HealthResponse:
    try:
        await redis_client.ping()  # type: ignore[misc]
        redis_status = "ok"
    except RedisError as e:
        print("Redis ping failed: %s", e)
        redis_status = "unavailable"
    return HealthResponse(status="ok", app_name=settings.app_name, redis=redis_status)


@app.post(
    "/tenants/",
    response_model=TenantCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tenant(
    tenant: TenantCreate, db: AsyncSession = Depends(get_db)
) -> TenantCreateResponse:
    db_tenant = Tenant(name=tenant.name)
    db.add(db_tenant)
    await db.flush()
    await db.refresh(db_tenant)
    return TenantCreateResponse(
        id=db_tenant.id, name=db_tenant.name, api_key=db_tenant.api_key
    )


async def get_current_tenant(
    api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Tenant | None:
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    result = await db.execute(select(Tenant).where(Tenant.api_key == api_key))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return tenant


@app.get("/tenants/me/", response_model=TenantGetResponse)
async def get_tenant(tenant: Tenant = Depends(get_current_tenant)) -> TenantGetResponse:
    return TenantGetResponse(
        id=tenant.id,
        name=tenant.name,
        signing_secret=tenant.signing_secret,
    )
