from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Populates persistence.base.Base.metadata with every own-schema table - importing the modules is
# enough (each one's class body registers on Base via its Mapped columns), the names themselves
# are never used directly here.
import persistence.game_settings  # noqa: F401
import persistence.games  # noqa: F401
import persistence.legacy_import  # noqa: F401
import persistence.users  # noqa: F401
from config import get_settings
from persistence.base import SCHEMA, Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# The app's DB role only has CREATE inside the `minigames` schema of its own database, not at the
# database level (see scripts/bootstrap_db_role.py) - alembic_version has to live there too, not
# in `public`, or a plain `alembic upgrade head` would fail with a permissions error.
_VERSION_TABLE_SCHEMA = SCHEMA


def _db_url() -> str:
    """Prefers an explicitly injected URL over Settings. scripts/bootstrap_db_role.py drives
    Alembic in-process via `set_main_option("sqlalchemy.url", ...)` and deliberately runs without
    JWT_SECRET/IMMICH_API_KEY, both of which Settings requires - so constructing Settings there
    would raise a ValidationError. Kept lazy (called inside the run_migrations_* functions) so
    merely importing this module never touches config."""
    return config.get_main_option("sqlalchemy.url") or get_settings().app_db_url


def _include_name(name: str | None, type_: str, parent_names: dict) -> bool:
    """Confines autogenerate to this app's own schema. `include_schemas=True` is required for
    autogenerate to see our tables at all (Base.metadata carries schema="minigames", so without it
    nothing matches and every table looks missing), but on its own it reflects EVERY schema in the
    database - which historically meant a `--revision --autogenerate` run against Immich's
    database would happily emit op.drop_table() for Immich's own tables. Harmless today (the app's
    database contains nothing else), kept as a hard guard because the failure mode is severe."""
    if type_ == "schema":
        return name == SCHEMA
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=_db_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=_VERSION_TABLE_SCHEMA,
        include_schemas=True,
        include_name=_include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Built from the same Settings-backed app_db_url the rest of the app uses (persistence/base.py's
    # get_app_engine) rather than alembic.ini's sqlalchemy.url, so there's one source of truth for
    # the connection string - unless a caller injected one, see _db_url.
    connectable = engine_from_config(
        {"sqlalchemy.url": _db_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=_VERSION_TABLE_SCHEMA,
            include_schemas=True,
            include_name=_include_name,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
