from fastapi import APIRouter, status

from app.schemas.health import HealthResponse
from app.services.health import get_health_status

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check() -> HealthResponse:
    return await get_health_status()
