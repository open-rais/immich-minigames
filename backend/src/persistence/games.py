"""
Own persistence layer for this app's games - separate from Immich's schema (see
immich_tables.py). Lives in its own Postgres schema (`minigames`) so this app's own migrations
never collide with Immich's (see docs/ARCHITECTURE/BACKEND.md).
"""

from datetime import datetime
from functools import lru_cache
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, MetaData, create_engine, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from config import Settings

SCHEMA = "minigames"


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


class GameModel(Base):
    __tablename__ = "games"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner: Mapped[str]
    game_type: Mapped[str]
    mode: Mapped[str]
    score: Mapped[int] = mapped_column(default=0)
    finished: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    rounds: Mapped[list["RoundModel"]] = relationship(
        back_populates="game",
        order_by="RoundModel.round_index",
        cascade="all, delete-orphan",
    )


class RoundModel(Base):
    __tablename__ = "rounds"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    game_id: Mapped[UUID] = mapped_column(ForeignKey(f"{SCHEMA}.games.id"))
    round_index: Mapped[int]
    # Null until the round is answered - see games/base.py.
    score_delta: Mapped[int | None] = mapped_column(default=None)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    game: Mapped[GameModel] = relationship(back_populates="rounds")


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(Settings().db_url)


def get_session_factory(engine: Engine | None = None) -> sessionmaker:
    return sessionmaker(bind=engine or get_engine())


def init_db(engine: Engine | None = None) -> None:
    """Creates this app's tables (idempotent). The `minigames` schema itself is provisioned once
    by docker/init-scripts/create_minigames_app_role.sh, not here - the app's own DB role
    deliberately has no CREATE privilege at the database level, only within that schema."""
    Base.metadata.create_all(engine or get_engine())


def reset_db(engine: Engine | None = None) -> None:
    """Drops and recreates this app's tables. Dev/test convenience only."""
    engine = engine or get_engine()
    Base.metadata.drop_all(engine)
    init_db(engine)
