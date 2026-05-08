from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infraestructure.db.models.settings import Base


class GameStatsModel(Base):
    __tablename__ = "game_stats"

    game_slug: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    mode_slug: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    best_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    times_played: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
