from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Populates persistence.base.Base.metadata with every own-schema table - importing the modules is
# enough (each one's class body registers on Base via its Mapped columns), the names themselves
# are never used directly here.
import persistence.games  # noqa: F401
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

# The app's DB role only has CREATE inside the `minigames` schema, not at the database level (see
# docker/init-scripts/create_minigames_app_role.sh) - alembic_version has to live there too, not
# in `public`, or a plain `alembic upgrade head` would fail with a permissions error.
_VERSION_TABLE_SCHEMA = SCHEMA


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
        url=get_settings().db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=_VERSION_TABLE_SCHEMA,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Built from the same Settings-backed db_url the rest of the app uses (persistence/base.py's
    # get_engine) rather than alembic.ini's sqlalchemy.url, so there's one source of truth for the
    # connection string.
    connectable = engine_from_config(
        {"sqlalchemy.url": get_settings().db_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=_VERSION_TABLE_SCHEMA,
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
