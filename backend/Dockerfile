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

EXPOSE 8000

# Runs pending Alembic migrations before starting uvicorn (--host 0.0.0.0 is required there, unlike
# the documented host dev command, so the port published by Docker actually reaches it instead of
# uvicorn's default 127.0.0.1 bind) - see docker-entrypoint.sh.
ENTRYPOINT ["./docker-entrypoint.sh"]
