from fastapi import FastAPI, status
from pydantic import BaseModel

from app.config import settings

app = FastAPI()


class HealthResponse(BaseModel):
    status: str
    app_name: str


@app.get("/ping", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", app_name=settings.app_name)
