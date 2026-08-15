FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY alembic ./alembic
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Packaged installs always emit structured JSON logs - config.py's
# LOG_FORMAT default of "console" is for bare `uv run uvicorn` dev only.
ENV LOG_FORMAT=json

EXPOSE 8000

# start-period covers docker-entrypoint.sh's `alembic upgrade head`, which runs before uvicorn
# even starts - without it, a long migration would report unhealthy on every upgrade. python3 (not
# curl/wget, absent from this base image) hits GET /api/v1/health; urlopen already raises - and so
# exits non-zero - on a non-2xx response, no extra plumbing needed.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

# Runs pending Alembic migrations before starting uvicorn (--host 0.0.0.0 is required there, unlike
# the documented host dev command, so the port published by Docker actually reaches it instead of
# uvicorn's default 127.0.0.1 bind) - see docker-entrypoint.sh.
ENTRYPOINT ["./docker-entrypoint.sh"]
