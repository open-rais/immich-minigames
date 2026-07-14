"""
Own persistence layer for this app's games - separate from Immich's schema (see
immich_tables.py). Lives in its own Postgres schema (`minigames`) so this app's own migrations
never collide with Immich's (see docs/ARCHITECTURE/BACKEND.md). Shared Base/engine/session
plumbing lives in persistence/base.py so other own-schema modules (e.g. users.py) can share it.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from persistence.base import SCHEMA, Base


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
    # Enforces one round per index within a game (the app assigns incremental indices in
    # create_next_round, but nothing at the DB level guaranteed it). Postgres does not auto-index FK
    # columns, so this composite unique also provides the index for "rounds of this game" lookups on
    # game_id.
    __table_args__ = (UniqueConstraint("game_id", "round_index"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    game_id: Mapped[UUID] = mapped_column(ForeignKey(f"{SCHEMA}.games.id"))
    round_index: Mapped[int]
    # Null until the round is answered - see games/base.py.
    score_delta: Mapped[int | None] = mapped_column(default=None)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    game: Mapped[GameModel] = relationship(back_populates="rounds")
