"""One-shot DB bootstrap: creates (or refreshes) the Postgres role the minigames backend runs as -
read-only on Immich's own `public` schema, full control over this app's own `minigames` schema - so
the long-running backend container never needs Immich's admin credentials (DB_USERNAME/DB_PASSWORD)
for anything. Connects directly to Postgres over the network (not `docker exec`), so it works
whether Immich's DB is this repo's own dev stack or a completely separate Immich deployment.

Run via `docker compose -f docker-compose.app.yml run --rm db-init` - also runs automatically
before `backend` on `docker compose up` (see the `db-init` service's `depends_on` there), and is
idempotent to re-run any time DB_APP_PASSWORD changes. See docs/ARCHITECTURE/BACKEND.md.
"""

import os
import sys

import psycopg
from psycopg import sql

SCHEMA = "minigames"

REQUIRED_VARS = [
    "DB_HOST",
    "DB_PORT",
    "DB_DATABASE_NAME",
    "DB_USERNAME",
    "DB_PASSWORD",
    "DB_APP_USERNAME",
    "DB_APP_PASSWORD",
]


def _load_env() -> dict[str, str]:
    missing = [name for name in REQUIRED_VARS if not os.environ.get(name)]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return {name: os.environ[name] for name in REQUIRED_VARS}


def main() -> None:
    env = _load_env()
    admin_url = (
        f"postgresql://{env['DB_USERNAME']}:{env['DB_PASSWORD']}"
        f"@{env['DB_HOST']}:{env['DB_PORT']}/{env['DB_DATABASE_NAME']}"
    )
    app_role = sql.Identifier(env["DB_APP_USERNAME"])
    password = sql.Literal(env["DB_APP_PASSWORD"])
    schema = sql.Identifier(SCHEMA)

    with psycopg.connect(admin_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (env["DB_APP_USERNAME"],))
        role_exists = cur.fetchone() is not None
        verb = "ALTER" if role_exists else "CREATE"
        cur.execute(sql.SQL(f"{verb} ROLE {{}} WITH LOGIN PASSWORD {{}}").format(app_role, password))

        cur.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(env["DB_DATABASE_NAME"]), app_role
            )
        )

        # Immich's own schema: read-only. Postgres 14 (unlike 15+) grants CREATE on public to
        # PUBLIC by default, which would otherwise let this role create its own tables there too.
        cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(app_role))
        cur.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(app_role))
        cur.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {}"
            ).format(app_role)
        )

        # This app's own schema: full control. Tables the role creates itself (the normal case,
        # via SQLAlchemy's create_all()) are owned by it automatically; the explicit GRANTs below
        # only matter for tables that already exist from before this role existed.
        cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(schema))
        cur.execute(sql.SQL("GRANT CREATE, USAGE ON SCHEMA {} TO {}").format(schema, app_role))
        cur.execute(sql.SQL("GRANT ALL ON ALL TABLES IN SCHEMA {} TO {}").format(schema, app_role))
        cur.execute(
            sql.SQL("GRANT ALL ON ALL SEQUENCES IN SCHEMA {} TO {}").format(schema, app_role)
        )
        cur.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT ALL ON TABLES TO {}").format(
                schema, app_role
            )
        )
        cur.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT ALL ON SEQUENCES TO {}").format(
                schema, app_role
            )
        )

    print(
        f"Role '{env['DB_APP_USERNAME']}' ready: read-only on 'public' (Immich), "
        f"full control on '{SCHEMA}'."
    )


if __name__ == "__main__":
    main()
