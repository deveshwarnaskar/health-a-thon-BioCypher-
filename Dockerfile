# ==============================================================================
# THALI + P.L.A.T.E. Multi-Stage Production Containerfile (Gate 10P-A)
# ==============================================================================
# Targets:
# - base:    Minimal Python runtime foundation + non-root security user
# - builder: Multi-stage dependency compiler using astral-sh/uv with locked deps
# - api:     Production FastAPI ASGI application container
# - worker:  Production Transactional Outbox worker container
# - migrate: Deterministic Alembic database migration runner container
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Base Runtime Image
# ------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS base

# Prevent Python from writing .pyc files and enable unbuffered standard I/O
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"

# Install minimal runtime dependencies (curl for healthchecks, ca-certificates for TLS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged system group and user
RUN groupadd --gid 10001 thali && \
    useradd --uid 10001 --gid thali --home-dir /app --shell /sbin/nologin --no-create-home thali

WORKDIR /app

# ------------------------------------------------------------------------------
# Stage 2: Dependency Builder
# ------------------------------------------------------------------------------
FROM base AS builder

# Install uv binary from official Astral image (pinned version)
COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /uvx /bin/

# Create application virtual environment
RUN uv venv /app/.venv

# Copy dependency specification files
COPY requirements.txt requirements.lock ./

# Install exact locked dependencies into virtual environment
RUN uv pip install --no-cache -r requirements.lock

# ------------------------------------------------------------------------------
# Stage 3: API Container
# ------------------------------------------------------------------------------
FROM base AS api

# Copy compiled virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code, configuration, and migrations
COPY --chown=thali:thali backend/ ./backend/
COPY --chown=thali:thali config/ ./config/
COPY --chown=thali:thali scripts/ ./scripts/
COPY --chown=thali:thali alembic.ini ./
COPY --chown=thali:thali docker/entrypoint-api.sh ./docker/

# Ensure entrypoint is executable
RUN chmod +x /app/docker/entrypoint-api.sh

# Switch to non-root runtime user
USER thali

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

ENTRYPOINT ["/bin/sh", "/app/docker/entrypoint-api.sh"]

# ------------------------------------------------------------------------------
# Stage 4: Transactional Outbox Worker Container
# ------------------------------------------------------------------------------
FROM base AS worker

# Copy compiled virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code, configuration, and migrations
COPY --chown=thali:thali backend/ ./backend/
COPY --chown=thali:thali config/ ./config/
COPY --chown=thali:thali scripts/ ./scripts/
COPY --chown=thali:thali alembic.ini ./
COPY --chown=thali:thali docker/entrypoint-worker.sh ./docker/

# Ensure entrypoint is executable
RUN chmod +x /app/docker/entrypoint-worker.sh

# Switch to non-root runtime user
USER thali

ENTRYPOINT ["/bin/sh", "/app/docker/entrypoint-worker.sh"]

# ------------------------------------------------------------------------------
# Stage 5: Database Migration Runner Container
# ------------------------------------------------------------------------------
FROM base AS migrate

# Copy compiled virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code, configuration, and migrations
COPY --chown=thali:thali backend/ ./backend/
COPY --chown=thali:thali config/ ./config/
COPY --chown=thali:thali scripts/ ./scripts/
COPY --chown=thali:thali alembic.ini ./
COPY --chown=thali:thali docker/entrypoint-migrate.sh ./docker/

# Ensure entrypoint is executable
RUN chmod +x /app/docker/entrypoint-migrate.sh

# Switch to non-root runtime user
USER thali

ENTRYPOINT ["/bin/sh", "/app/docker/entrypoint-migrate.sh"]
