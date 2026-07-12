#!/usr/bin/env bash
# Creates (or refreshes the password of) the read-only Postgres role the minigames backend
# uses to query Immich's database - see docs/ARCHITECTURE/BACKEND.md. Run once after
# `docker compose up -d`, and again any time DB_RO_PASSWORD changes in .env. Idempotent.
set -euo pipefail

cd "$(dirname "$0")/../.."
source .env

docker exec -i immich-minigames-postgres psql -U "$DB_USERNAME" -d "$DB_DATABASE_NAME" <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_RO_USERNAME') THEN
    CREATE ROLE "$DB_RO_USERNAME" WITH LOGIN PASSWORD '$DB_RO_PASSWORD';
  ELSE
    ALTER ROLE "$DB_RO_USERNAME" WITH PASSWORD '$DB_RO_PASSWORD';
  END IF;
END
\$\$;

-- Postgres 14 (unlike 15+) grants CREATE on the public schema to PUBLIC by default, which would
-- otherwise let this role create its own tables despite being "read-only".
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

GRANT CONNECT ON DATABASE "$DB_DATABASE_NAME" TO "$DB_RO_USERNAME";
GRANT USAGE ON SCHEMA public TO "$DB_RO_USERNAME";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO "$DB_RO_USERNAME";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO "$DB_RO_USERNAME";
SQL

echo "Role '$DB_RO_USERNAME' ready with read-only access to '$DB_DATABASE_NAME'."
