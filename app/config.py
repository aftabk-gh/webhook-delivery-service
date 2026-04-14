from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "webhook-delivery-service"
    debug: bool = False
    database_url: str
    db_pool_size: int = 10
    db_max_overflow: int = 20
    redis_url: str
    secret_key: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
