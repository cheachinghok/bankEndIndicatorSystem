from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache
def get_settings() -> Settings:
    return Settings()
