# syntax=docker/dockerfile:1
# Shared image for API and Celery worker (EP01-02).

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/README.md ./
COPY backend/src ./src
COPY backend/tests ./tests
COPY backend/scripts ./scripts
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic

RUN pip install ".[dev]"

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
