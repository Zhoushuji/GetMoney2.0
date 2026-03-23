from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "LeadGen System"
    environment: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    secret_key: str = "change_me_in_production"
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadgen"
    redis_url: str = "redis://127.0.0.1:6379/0"
    serper_api_key: str = ""
    bing_api_key: str = ""
    backend_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost", "http://127.0.0.1", "http://localhost:3000", "http://127.0.0.1:3000"])
    proxy_list: str = ""
    proxy_api_url: str = ""
    enable_proxy: bool = False
    enable_robots_check: bool = True
    playwright_headless: bool = True
    max_concurrent_searches: int = 5
    max_concurrent_scrapers: int = 3
    request_delay_min: int = 2
    request_delay_max: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
