# syntax=docker/dockerfile:1.7
#
# Multi-stage build for the siwe-django showcase.
#
#   stage 1: build the Vite/React frontend with bun, output dist/ -> /frontend
#   stage 2: install siwe-django + showcase deps, copy the built dist into
#            backend/showcase/static_frontend/, run gunicorn behind whitenoise
#
# Build context = repo root, e.g.
#   fly deploy --config examples/showcase/fly.toml --dockerfile examples/showcase/Dockerfile
#

# -----------------------------------------------------------------------------
# Stage 1: frontend
# -----------------------------------------------------------------------------
FROM oven/bun:1 AS frontend
WORKDIR /frontend

ENV VITE_BASE=/static/

COPY examples/showcase/frontend/package.json examples/showcase/frontend/package-lock.json* ./
RUN bun install --frozen-lockfile || bun install

COPY examples/showcase/frontend/ ./
RUN bun run build

# -----------------------------------------------------------------------------
# Stage 2: runtime
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    DJANGO_SETTINGS_MODULE=showcase.settings \
    SIWE_DEMO_DEBUG=false \
    SIWE_DEMO_SECURE_COOKIES=true \
    SIWE_DEMO_USE_X_FORWARDED_PROTO=true \
    SIWE_DEMO_DATABASE_PATH=/data/db.sqlite3

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*

# Install siwe-django (this repo) + production server deps. Copy only what
# pip needs first so the heavy install layer stays cached when only the
# showcase app changes.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --upgrade pip \
 && pip install ".[drf]" "gunicorn>=22" "whitenoise[brotli]>=6"

# Showcase code + the built frontend bundle
COPY examples/showcase/ ./examples/showcase/
COPY --from=frontend /frontend/dist ./examples/showcase/backend/showcase/static_frontend

WORKDIR /app/examples/showcase/backend
ENV PYTHONPATH=/app/examples/showcase/backend

RUN chmod +x /app/examples/showcase/entrypoint.sh \
 && python manage.py collectstatic --noinput

EXPOSE 8080
CMD ["/app/examples/showcase/entrypoint.sh"]
