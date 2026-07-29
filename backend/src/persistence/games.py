"""
Own persistence layer for this app's games - in this app's own Postgres database, a different one
from Immich's (see persistence/base.py for why, and immich_tables.py for the read-only side).
Shared Base/engine/session plumbing lives in persistence/base.py so other own-database modules
(e.g. users.py) can share it.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from persistence.base import SCHEMA, Base

# Roadmap #G (daily games) - GameModel.daily_challenge_id below is a real FK to this table, which
# must already be registered in Base.metadata by the time tests' reset_db()/create_all() (or a
# real `alembic upgrade`) runs. Nothing else in this module's own import chain pulls
# persistence.daily in on its own (unlike UserModel, which every request path already imports via
# services/auth_service.py) - see persistence/daily.py.
from persistence.daily import DailyChallengeModel  # noqa: F401


class GameModel(Base):
    __tablename__ = "games"
    # Both indexes back GamesService.get_personal_records's per-(owner-or-user, game_type, mode)
    # MAX(score) lookup - one per filter branch (anonymous X-Owner-Id vs logged-in user_id).
    __table_args__ = (
        Index("ix_games_owner_type_mode", "owner", "game_type", "mode"),
        Index("ix_games_user_type_mode", "user_id", "game_type", "mode"),
        # Roadmap #G - "one daily attempt per (challenge, player)" enforced at the DB level, not
        # just in GamesService.create_daily_game. Two partial indexes (mirroring the
        # owner-vs-user_id branching every other per-player query in this file already does)
        # rather than one plain UNIQUE(daily_challenge_id, user_id): Postgres never treats two NULLs
        # as equal, so a plain unique constraint on that pair would let unlimited anonymous
        # (user_id IS NULL) games through for the same challenge - the owner-keyed index below is
        # what actually catches those.
        Index(
            "uq_games_daily_user",
            "daily_challenge_id",
            "user_id",
            unique=True,
            postgresql_where=text("daily_challenge_id IS NOT NULL AND user_id IS NOT NULL"),
        ),
        Index(
            "uq_games_daily_owner",
            "daily_challenge_id",
            "owner",
            unique=True,
            postgresql_where=text("daily_challenge_id IS NOT NULL AND user_id IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner: Mapped[str]
    # Set only when the game-creation request was authenticated (see api/api.py's create_game) -
    # anonymous play leaves this null and keeps working off `owner` alone, exactly as before this
    # column existed. A real FK (unlike skin_person_id on UserModel) since UserModel lives in this
    # same app database, not Immich's.
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.users.id"), default=None)
    game_type: Mapped[str]
    mode: Mapped[str]
    score: Mapped[int] = mapped_column(default=0)
    finished: Mapped[bool] = mapped_column(default=False)
    # Roadmap #e - set when a new game of the same (owner-or-user, game_type, mode) starts while
    # this one was still unfinished (GamesService._abandon_active_games). Never becomes True at the
    # same time finished does, so get_personal_records/get_leaderboard need no changes.
    abandoned: Mapped[bool] = mapped_column(default=False)
    # Roadmap #G - set only for a game created through the daily flow (GamesService.
    # create_daily_game), pointing at the shared challenge content it was instantiated from. NULL
    # for every normal game, exactly as before this column existed - see GamesService's
    # daily_challenge_id IS NULL filters on get_personal_records/get_leaderboard/get_current_game/
    # _abandon_active_games (daily games live in a separate "world", docs/TODO/DAILY-GAMES.md §4.5).
    daily_challenge_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.daily_challenges.id"), default=None
    )
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
