from redis.exceptions import RedisError

from app.config import settings
from app.core.logging import get_logger
from app.core.redis import redis_client
from app.schemas.health import HealthResponse

logger = get_logger(__name__)


async def get_health_status() -> HealthResponse:
    try:
        await redis_client.ping()  # type: ignore[misc]
        redis_status = "ok"
    except RedisError as exc:
        logger.warning(
            "redis_ping_failed",
            tenant_id="system",
            error=str(exc),
        )
        redis_status = "unavailable"

    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        redis=redis_status,
    )
