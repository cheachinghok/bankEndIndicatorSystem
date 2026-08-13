import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.redis import get_redis
from app.db.session import dispose_engine, get_session


def _configure_logging(level: str) -> None:
    root = logging.getLogger()
    if root.handlers:
        # Uvicorn already added its own handler — set our app loggers instead.
        logging.getLogger("app").setLevel(level.upper())
        return
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _configure_logging(settings.log_level)
    yield
    await dispose_engine()


app = FastAPI(
    title="Gold Signals API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/healthz")
async def healthz(session: AsyncSession = Depends(get_session)):
    """Deep health check — Railway uses this to gate traffic to the instance.

    Verifies DB and Redis connectivity. Returns 503 if any dependency is down
    so bad deploys fail loudly instead of serving broken responses.
    """
    checks: dict[str, str] = {"api": "ok"}
    try:
        await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["db"] = f"error: {e.__class__.__name__}"

    redis = get_redis()
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["redis"] = f"error: {e.__class__.__name__}"
    finally:
        await redis.aclose()

    all_ok = all(v == "ok" for v in checks.values())
    return checks if all_ok else JSONResponse(checks, status_code=503)
