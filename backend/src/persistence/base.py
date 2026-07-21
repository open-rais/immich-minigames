"""
Shared SQLAlchemy plumbing for this app's own persistence layer, which lives in its own Postgres
DATABASE (`DB_APP_DATABASE_NAME`, default `minigames`) - not inside Immich's, because Immich's
`pg_dump --clean --if-exists` backup would otherwise sweep it up and choke on it at restore time
(see docs/ARCHITECTURE/BACKEND.md). Immich's own database is reached through a second, read-only
engine in immich_db.py; nothing here knows about it.

Tables still sit in a `minigames` SCHEMA inside that database rather than `public` - the app owns
the whole database, so this is cosmetic, but it keeps every already-applied migration (which
hardcodes `schema=`) valid and unmodified.

Split out from games.py so other own-database modules (e.g. users.py) can declare models against
the same `Base` without a second engine.
"""

from functools import lru_cache

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import get_settings

SCHEMA = "minigames"


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


@lru_cache(maxsize=1)
def get_app_engine() -> Engine:
    """Engine for this app's own database. The backend runs two pools, one per database - this one
    and immich_db.py's read-only one; they share credentials (a single login role) but nothing
    else. pool_pre_ping=True since Postgres restarts/idle-closed connections shouldn't surface as
    a request-time error."""
    return create_engine(get_settings().app_db_url, pool_pre_ping=True)


def get_session_factory(engine: Engine | None = None) -> sessionmaker:
    return sessionmaker(bind=engine or get_app_engine())


def init_db(engine: Engine | None = None) -> None:
    """Creates this app's tables (idempotent). The database and the `minigames` schema inside it
    are both provisioned by scripts/bootstrap_db_role.py, not here - the app's own DB role
    deliberately has no CREATE privilege at the database level, only within that schema."""
    Base.metadata.create_all(engine or get_app_engine())


def reset_db(engine: Engine | None = None) -> None:
    """Drops and recreates this app's tables. Dev/test convenience only."""
    engine = engine or get_app_engine()
    Base.metadata.drop_all(engine)
    init_db(engine)
