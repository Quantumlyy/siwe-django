#!/usr/bin/env bash
set -euo pipefail

# Ensure the SQLite parent directory exists when running on a Fly volume.
DB_DIR="$(dirname "${SIWE_DEMO_DATABASE_PATH:-/data/db.sqlite3}")"
mkdir -p "$DB_DIR"

python manage.py migrate --noinput

exec gunicorn showcase.wsgi:application \
    --bind "0.0.0.0:${PORT:-8080}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-30}" \
    --access-logfile - \
    --error-logfile -
