# syntax=docker/dockerfile:1
#
# Multi-stage build for the DataSentinel backend (FastAPI + SQLAlchemy,
# PostgreSQL in production). See backend/README.md's "Database portability"
# section for why the schema/ORM work against both SQLite (tests) and
# Postgres (production).
#
# Schema migration is intentionally NOT run here (no `alembic upgrade head`
# baked into ENTRYPOINT/CMD). backend/datasentinel_backend/main.py's module
# docstring explains why: implicit DDL-on-boot races when multiple replicas
# start concurrently and bypasses migration history tracking. Migrations are
# run as an explicit one-shot step by the `backend-migrate` service in
# docker-compose.yml instead.

# ---- Build stage: resolve and install dependencies into a venv ----
FROM python:3.12-slim AS builder

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# hatchling (the build backend declared in pyproject.toml) needs README.md
# present because pyproject.toml declares readme = "README.md".
COPY pyproject.toml README.md ./
COPY datasentinel_backend ./datasentinel_backend
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ---- Runtime stage ----
FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/datasentinel_backend ./datasentinel_backend
COPY --from=builder /build/alembic ./alembic
COPY --from=builder /build/alembic.ini ./alembic.ini

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8000

# Default command runs the API. The `backend-migrate` compose service uses
# this same image but overrides this with `alembic upgrade head`.
CMD ["uvicorn", "datasentinel_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
