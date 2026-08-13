import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _test_env() -> None:
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://gold:gold@localhost:5432/gold_signals",
    )
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("OANDA_API_TOKEN", "")
