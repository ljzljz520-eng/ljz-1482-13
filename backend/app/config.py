"""应用配置：全部来自环境变量，容器内通过服务名访问依赖。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://charapp:charapp@db:5432/charstudio"
    jwt_secret: str = "charstudio-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    media_dir: str = "/data/media"
    # 封面派生任务的模拟处理延迟（秒），便于验收“旧任务晚到”
    cover_job_delay_seconds: float = 4.0
    # 置为 true 时 worker 会按任务参数让指定任务失败，用于验收“素材生成失败”
    enable_failure_injection: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
