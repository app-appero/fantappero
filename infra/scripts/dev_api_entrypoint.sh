#!/bin/sh
# Apply pending migrations, then start the API (local Compose).
set -e

echo "Applying database migrations..."
python -m alembic upgrade head

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
