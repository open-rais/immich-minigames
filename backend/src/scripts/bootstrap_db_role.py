"""One-shot DB bootstrap: provisions the Postgres role and the database the minigames backend runs
against, so the long-running backend container never needs Immich's admin credentials
(DB_USERNAME/DB_PASSWORD) for anything.

This app's tables live in their OWN DATABASE (DB_APP_DATABASE_NAME, default `minigames`) on the
same Postgres instance as Immich - never inside Immich's database. Immich backs up with
`pg_dump --clean --if-exists` scoped to its own database, so tables kept in there end up in
Immich's dumps and break its restore (see scripts/migrate_legacy_schema.py's module docstring for
the full failure). Installs created before that split are migrated automatically here: this script
is the only component holding admin credentials, and therefore the only one able to drop a schema
the app's own role does not own.

The app role gets:
  - Immich's database: `pg_read_all_data` - SELECT and nothing else. Granted via role membership
    rather than explicit GRANTs on `public` because membership lives in `pg_auth_members` at the
    cluster level, so Immich's database keeps zero references to this app in its own dumps. It also
    stops the grant going stale when an Immich upgrade adds a table.
  - Its own database: full control inside the `minigames` schema, no CREATE at the database level.

Connects directly to Postgres over the network (not `docker exec`), so it works whether Immich's DB
is this repo's own dev stack or a completely separate Immich deployment.

Run via `docker compose -f docker-compose.app.yml run --rm db-init` - also runs automatically
before `backend` on `docker compose up` (see the `db-init` service's `depends_on` there), and is
idempotent to re-run any time DB_APP_PASSWORD changes. See docs/ARCHITECTURE/BACKEND.md.
"""

import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from scripts.migrate_legacy_schema import LegacyMigrationError, migrate_legacy_schema

SCHEMA = "minigames"
DEFAULT_APP_DATABASE = "minigames"

REQUIRED_VARS = [
    "DB_DATABASE_NAME",
    "DB_USERNAME",
    "DB_PASSWORD",
    "DB_APP_USERNAME",
    "DB_APP_PASSWORD",
]

# Defaulted to match config.py's Settings, so running this by hand against a local dev stack works
# with the same .env the backend uses - docker-compose.app.yml passes both explicitly anyway.
OPTIONAL_VARS = {
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_APP_DATABASE_NAME": DEFAULT_APP_DATABASE,
}


def _load_env() -> dict[str, str]:
    missing = [name for name in REQUIRED_VARS if not os.environ.get(name)]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    env = {name: os.environ[name] for name in REQUIRED_VARS}
    # DB_APP_DATABASE_NAME in particular must stay optional: an existing install upgrading with
    # `docker compose pull && up -d` won't have it in its .env, and failing here would leave the
    # backend permanently down behind its `service_completed_successfully` dependency.
    for name, default in OPTIONAL_VARS.items():
        env[name] = os.environ.get(name) or default
    return env


def _url(env: dict[str, str], *, user: str, password: str, database: str) -> str:
    return f"postgresql://{user}:{password}@{env['DB_HOST']}:{env['DB_PORT']}/{database}"


def _configure_immich_database(cur: psycopg.Cursor, env: dict[str, str]) -> None:
    """Everything that happens inside Immich's own database. Read access only."""
    app_role = sql.Identifier(env["DB_APP_USERNAME"])
    password = sql.Literal(env["DB_APP_PASSWORD"])

    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (env["DB_APP_USERNAME"],))
    role_exists = cur.fetchone() is not None
    verb = "ALTER" if role_exists else "CREATE"
    cur.execute(sql.SQL(f"{verb} ROLE {{}} WITH LOGIN PASSWORD {{}}").format(app_role, password))

    cur.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(env["DB_DATABASE_NAME"]), app_role
        )
    )

    # Postgres 14 (unlike 15+) grants CREATE on public to PUBLIC by default. Kept even though the
    # app role no longer needs to create anything here - it is the only thing stopping any
    # unprivileged role in Immich's database from doing so. This ACL names no role of ours, so it
    # survives a dump/restore anywhere.
    cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")

    cur.execute(sql.SQL("GRANT pg_read_all_data TO {}").format(app_role))

    # Undo the explicit grants earlier versions of this script wrote into Immich's database. They
    # are ACLs naming our role, and pg_dump includes ACLs - leaving them would keep this app
    # present in every Immich backup, which is exactly what the split exists to end. Harmless
    # no-ops on a fresh install.
    cur.execute(
        sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM {}").format(
            app_role
        )
    )
    cur.execute(
        sql.SQL("REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM {}").format(app_role)
    )
    cur.execute(sql.SQL("REVOKE USAGE ON SCHEMA public FROM {}").format(app_role))

    # A guard rail against programming mistakes, NOT a security boundary: the role can still
    # `SET TRANSACTION READ WRITE` on itself. The real boundary is pg_read_all_data granting SELECT
    # and nothing else. Applied before the legacy migration runs on purpose - see main().
    cur.execute(
        sql.SQL("ALTER ROLE {} IN DATABASE {} SET default_transaction_read_only = on").format(
            app_role, sql.Identifier(env["DB_DATABASE_NAME"])
        )
    )


def _create_app_database(cur: psycopg.Cursor, env: dict[str, str]) -> None:
    """Creates this app's own database if absent. Must run with autocommit - Postgres forbids
    CREATE DATABASE inside a transaction block, and there is no IF NOT EXISTS form."""
    app_db = env["DB_APP_DATABASE_NAME"]
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (app_db,))
    if cur.fetchone() is None:
        # No TEMPLATE/ENCODING/LC_* overrides: template1's locale matches the rest of the cluster,
        # including Immich's database, and users.email/username carry collation-sensitive unique
        # indexes that a mismatched locale would order differently.
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(app_db)))
        print(f"Created database '{app_db}'.")

    cur.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(app_db), sql.Identifier(env["DB_APP_USERNAME"])
        )
    )


def _configure_app_database(cur: psycopg.Cursor, env: dict[str, str]) -> None:
    """Everything that happens inside this app's own database."""
    app_role = sql.Identifier(env["DB_APP_USERNAME"])
    schema = sql.Identifier(SCHEMA)

    # Same Postgres 14 wart as in Immich's database.
    cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")

    # Deliberately no AUTHORIZATION clause: with IF NOT EXISTS it would not change the owner of an
    # already-existing schema, so fresh and re-run paths would end up with different owners. The
    # schema stays admin-owned, which keeps db-init the sole privileged provisioner and denies the
    # app role the ability to drop its own schema. The tables inside it are owned by the app role,
    # since Alembic creates them on the app role's connection (see _run_migrations).
    cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(schema))
    cur.execute(sql.SQL("GRANT CREATE, USAGE ON SCHEMA {} TO {}").format(schema, app_role))
    cur.execute(sql.SQL("GRANT ALL ON ALL TABLES IN SCHEMA {} TO {}").format(schema, app_role))
    cur.execute(sql.SQL("GRANT ALL ON ALL SEQUENCES IN SCHEMA {} TO {}").format(schema, app_role))
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


def _guard_foreign_database(env: dict[str, str], app_url: str) -> None:
    """Refuses to adopt a pre-existing, unrelated database that happens to share our name."""
    with psycopg.connect(app_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') LIMIT 1"
        )
        if cur.fetchone() is None:
            return  # empty database, nothing to adopt
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name IN "
            "('alembic_version', 'games', 'users', 'rounds', 'game_settings') LIMIT 1",
            (SCHEMA,),
        )
        if cur.fetchone() is None:
            print(
                f"Refusing to use database '{env['DB_APP_DATABASE_NAME']}': it already exists, "
                "contains tables, and none of them are this app's. Point DB_APP_DATABASE_NAME at "
                "a different name, or drop that database if it is not in use.",
                file=sys.stderr,
            )
            sys.exit(1)


def _run_migrations(app_url: str) -> None:
    """Brings this app's own database up to head, so the legacy copy has tables to land in.

    Runs here rather than only in the backend's entrypoint because the copy below needs the target
    schema to exist, and `backend` starts after `db-init` completes. Deliberately on the APP role's
    connection, not the admin one: `GRANT ALL ON TABLES` confers DML, not ownership, and
    ALTER/DROP TABLE require ownership - so tables created by admin here would make the next
    migration that adds a column fail with `must be owner of table`, and only at that future
    release. The backend's entrypoint keeps its own `alembic upgrade head`; it is a no-op after
    this, but still covers the manual/dev path where db-init isn't used.
    """
    from alembic import command
    from alembic.config import Config

    # /app/alembic.ini in the container (Dockerfile WORKDIR /app), backend/alembic.ini in a dev
    # checkout - both are two levels up from src/scripts/.
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    # alembic/env.py prefers this over Settings, which db-init cannot construct: it is deliberately
    # given no JWT_SECRET or IMMICH_API_KEY, both of which Settings requires.
    cfg.set_main_option("sqlalchemy.url", app_url.replace("postgresql://", "postgresql+psycopg://"))
    command.upgrade(cfg, "head")


def main() -> None:
    env = _load_env()
    admin_immich_url = _url(
        env,
        user=env["DB_USERNAME"],
        password=env["DB_PASSWORD"],
        database=env["DB_DATABASE_NAME"],
    )
    admin_app_url = _url(
        env,
        user=env["DB_USERNAME"],
        password=env["DB_PASSWORD"],
        database=env["DB_APP_DATABASE_NAME"],
    )
    app_app_url = _url(
        env,
        user=env["DB_APP_USERNAME"],
        password=env["DB_APP_PASSWORD"],
        database=env["DB_APP_DATABASE_NAME"],
    )

    # Immich's database: role, read access, and the read-only guard rail. Doing this BEFORE the
    # legacy migration is deliberate - it fences an older backend container, which may still be
    # running and serving requests during `docker compose up -d`, out of the legacy schema for the
    # duration of the copy. Do not reorder.
    with psycopg.connect(admin_immich_url, autocommit=True) as conn, conn.cursor() as cur:
        _configure_immich_database(cur, env)
        _create_app_database(cur, env)

    _guard_foreign_database(env, admin_app_url)

    with psycopg.connect(admin_app_url, autocommit=True) as conn, conn.cursor() as cur:
        _configure_app_database(cur, env)

    _run_migrations(app_app_url)

    try:
        report = migrate_legacy_schema(
            source_url=admin_immich_url,
            target_url=app_app_url,
            source_database=env["DB_DATABASE_NAME"],
        )
    except LegacyMigrationError as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        sys.exit(1)

    print(
        f"Role '{env['DB_APP_USERNAME']}' ready: read-only on '{env['DB_DATABASE_NAME']}' "
        f"(Immich), full control on '{env['DB_APP_DATABASE_NAME']}.{SCHEMA}'. "
        f"Legacy migration: {report.action}."
    )


if __name__ == "__main__":
    main()
