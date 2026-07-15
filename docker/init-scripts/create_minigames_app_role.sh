#!/usr/bin/env bash
# Creates (or refreshes) the single Postgres role the minigames backend runs as: read-only on
# Immich's own schema (`public`), full control over this app's own schema (`minigames`) - so the
# backend never needs Immich's admin credentials (DB_USERNAME/DB_PASSWORD) for anything. See
# docs/ARCHITECTURE/BACKEND.md. Run once after `docker compose up -d`, and again any time
# DB_APP_PASSWORD changes in .env. Idempotent - safe to re-run, never drops data.
set -euo pipefail

cd "$(dirname "$0")/../.."
source .env

docker exec -i immich-minigames-postgres psql -U "$DB_USERNAME" -d "$DB_DATABASE_NAME" -v pw="$DB_APP_PASSWORD" <<SQL
-- The password goes in via psql's own :'pw' variable substitution + format('%L', ...), not bash
-- interpolation like the identifiers below - a bare bash \$DB_APP_PASSWORD dropped into a SQL
-- string literal would break (or inject into) the statement if the password ever contained a
-- single quote. format('%L', :'pw') has psql itself produce a correctly-escaped literal for
-- whatever the password actually is, and \gexec runs the single CREATE/ALTER statement the SELECT
-- below produces (a plain DO \$\$ block won't work here - psql doesn't substitute :'vars' inside
-- dollar-quoted bodies).
SELECT format('CREATE ROLE %I WITH LOGIN PASSWORD %L', '$DB_APP_USERNAME', :'pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_APP_USERNAME')
UNION ALL
SELECT format('ALTER ROLE %I WITH PASSWORD %L', '$DB_APP_USERNAME', :'pw')
WHERE EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_APP_USERNAME')
\gexec

GRANT CONNECT ON DATABASE "$DB_DATABASE_NAME" TO "$DB_APP_USERNAME";

-- Immich's own schema: read-only. Postgres 14 (unlike 15+) grants CREATE on public to PUBLIC by
-- default, which would otherwise let this role create its own tables there too.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO "$DB_APP_USERNAME";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO "$DB_APP_USERNAME";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO "$DB_APP_USERNAME";

-- This app's own schema: full control. Tables the role creates itself (the normal case, via
-- SQLAlchemy's create_all()) are owned by it automatically; the explicit GRANTs below only matter
-- for tables that already exist from before this role existed.
CREATE SCHEMA IF NOT EXISTS minigames;
GRANT CREATE, USAGE ON SCHEMA minigames TO "$DB_APP_USERNAME";
GRANT ALL ON ALL TABLES IN SCHEMA minigames TO "$DB_APP_USERNAME";
GRANT ALL ON ALL SEQUENCES IN SCHEMA minigames TO "$DB_APP_USERNAME";
ALTER DEFAULT PRIVILEGES IN SCHEMA minigames GRANT ALL ON TABLES TO "$DB_APP_USERNAME";
ALTER DEFAULT PRIVILEGES IN SCHEMA minigames GRANT ALL ON SEQUENCES TO "$DB_APP_USERNAME";
SQL

echo "Role '$DB_APP_USERNAME' ready: read-only on 'public' (Immich), full control on 'minigames'."
