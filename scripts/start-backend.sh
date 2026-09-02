#!/bin/sh
# Run migrations (PostgreSQL) then start the API. For SQLite dev the app creates tables itself.
set -e
cd /app/backend
case "$DATABASE_URL" in
  sqlite*) echo "SQLite database: tables created by the application" ;;
  *) alembic upgrade head ;;
esac
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
