"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://workbench:workbench@db:5432/workbench"
    media_root: str = "/data/media"
    token_secret: str = "change-me-in-production"
    enable_worker: bool = True
    worker_interval_seconds: float = 3.0
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
