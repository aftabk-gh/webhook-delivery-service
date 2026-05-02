from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes.endpoints import router as endpoint_router
from app.api.routes.health import router as health_router
from app.api.routes.tenants import router as tenant_router
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger
from app.core.redis import redis_client, verify_redis

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        await verify_redis()
    except RedisError as exc:
        logger.warning(
            "redis_unavailable_on_startup",
            tenant_id="system",
            error=str(exc),
        )
    yield
    await redis_client.aclose()


app = FastAPI(lifespan=lifespan)
app.include_router(endpoint_router)
app.include_router(health_router)
app.include_router(tenant_router)


@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "code": exc.code},
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(
    _: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail), "code": "HTTP_ERROR"},
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": str(exc), "code": "VALIDATION_ERROR"},
    )
