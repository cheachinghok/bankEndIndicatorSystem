from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_pg_url(url: str) -> str:
    """Rewrite Postgres URLs to use the asyncpg driver.

    Railway (and most managed Postgres providers) inject DATABASE_URL as
    `postgres://...` or `postgresql://...`. SQLAlchemy async needs
    `postgresql+asyncpg://...`. We normalize here in one place so nothing
    downstream has to care.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    oanda_api_token: str = Field(default="", description="OANDA v20 personal access token")
    oanda_account_id: str = Field(default="", description="OANDA account id (fxTrade or fxPractice)")
    oanda_environment: Literal["practice", "live"] = "practice"
    oanda_api_url: str = "https://api-fxpractice.oanda.com"

    database_url: str = "postgresql+asyncpg://gold:gold@localhost:5432/gold_signals"
    redis_url: str = "redis://localhost:6379/0"

    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _fix_pg_scheme(cls, v: str) -> str:
        return _normalize_pg_url(v)


@lru_cache
def get_settings() -> Settings:
    return Settings()
