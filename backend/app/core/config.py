from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_pg_url(url: str) -> str:
    """Rewrite Postgres URLs to use the asyncpg driver and asyncpg-compatible params.

    Railway/Neon/most managed providers inject DATABASE_URL with the psycopg2
    dialect and query params like `sslmode=require` / `channel_binding=require`.
    asyncpg doesn't recognize those — it uses `ssl=` instead. We normalize here
    in one place so nothing downstream has to care.
    """
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    parsed = urlparse(url)
    if parsed.query:
        params = parse_qsl(parsed.query, keep_blank_values=True)
        cleaned: list[tuple[str, str]] = []
        need_ssl_require = False
        for k, v in params:
            if k == "sslmode":
                # psycopg2 → asyncpg translation
                if v in ("require", "verify-ca", "verify-full"):
                    need_ssl_require = True
                continue  # drop the sslmode param either way
            if k == "channel_binding":
                # Not supported by asyncpg — drop silently
                continue
            cleaned.append((k, v))
        if need_ssl_require and not any(k == "ssl" for k, _ in cleaned):
            cleaned.append(("ssl", "require"))
        parsed = parsed._replace(query=urlencode(cleaned))
        url = urlunparse(parsed)
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
