"""
Shared SQLAlchemy plumbing for this app's own persistence layer - separate from Immich's schema
(see immich_tables.py). Lives in its own Postgres schema (`minigames`) so this app's own
migrations never collide with Immich's (see docs/ARCHITECTURE/BACKEND.md). Split out from
games.py so other own-schema modules (e.g. users.py) can declare models against the same `Base`
without a second schema/engine.
"""

from functools import lru_cache

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import Settings

SCHEMA = "minigames"


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(Settings().db_url)


def get_session_factory(engine: Engine | None = None) -> sessionmaker:
    return sessionmaker(bind=engine or get_engine())


def init_db(engine: Engine | None = None) -> None:
    """Creates this app's tables (idempotent). The `minigames` schema itself is provisioned by
    scripts/bootstrap_db_role.py, not here - the app's own DB role deliberately has no CREATE
    privilege at the database level, only within that schema."""
    Base.metadata.create_all(engine or get_engine())


def reset_db(engine: Engine | None = None) -> None:
    """Drops and recreates this app's tables. Dev/test convenience only."""
    engine = engine or get_engine()
    Base.metadata.drop_all(engine)
    init_db(engine)
