import redis.asyncio as aioredis

from app.config import settings

redis_client = aioredis.from_url(
    url=settings.redis_url, encoding="utf-8", decode_responses=True
)


async def verify_redis() -> None:
    await redis_client.ping()  # type: ignore[misc]
