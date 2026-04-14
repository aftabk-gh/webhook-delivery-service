from fastapi import FastAPI, status
from pydantic import BaseModel

from app.config import get_settings

app = FastAPI()
settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    app_name: str


@app.get("/ping", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", app_name=settings.app_name)
