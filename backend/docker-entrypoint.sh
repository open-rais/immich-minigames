#!/bin/sh
set -e

# Applies pending migrations on every container start - safe whether this is a brand new database
# (alembic/versions/0001_baseline.py creates everything) or an upgrade from any prior version
# (already-applied migrations are no-ops), so a plain `docker compose pull && docker compose up -d`
# always ends up on the correct schema without any manual step.
#
# --frozen --no-dev matches the sync done at image build time - without them, `uv run` re-syncs
# against the full lockfile (including dev-only deps like pytest's) and reaches out to PyPI on
# every container start, which a production container shouldn't depend on.
uv run --frozen --no-dev alembic upgrade head

exec uv run --frozen --no-dev uvicorn main:app --app-dir src --host 0.0.0.0 --port 8000
