# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: build-essential for any C extensions during install.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package resolution.
RUN pip install --no-cache-dir uv

# Install project dependencies first, keeping layer cache warm across code changes.
COPY pyproject.toml ./
COPY app ./app
RUN uv pip install --system -e .

# Bring in migrations and any remaining assets.
COPY alembic.ini ./
COPY tests ./tests

# Railway injects PORT. Default 8000 for local runs.
EXPOSE 8000

# Default CMD serves the API. Override in Railway for the workers service:
#   python -m app.workers.main
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
