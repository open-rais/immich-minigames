from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.game_stats import GameStats
from src.domain.repositories.game_stats_repository import GameStatsRepository
from src.infraestructure.db.models.game_stats import GameStatsModel


class SQLAlchemyGameStatsRepository(GameStatsRepository):
    """SQLAlchemy implementation of GameStatsRepository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize game stats repository.
        
        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def get(self, game_slug: str, mode_slug: str) -> GameStats | None:
        """Get stats for a game mode."""
        query = select(GameStatsModel).where(
            GameStatsModel.game_slug == game_slug,
            GameStatsModel.mode_slug == mode_slug,
        )
        result = await self.session.execute(query)
        row = result.scalar_one_or_none()

        if not row:
            return None

        return GameStats(
            game_slug=row.game_slug,
            mode_slug=row.mode_slug,
            best_score=row.best_score,
            times_played=row.times_played,
        )

    async def save(self, stats: GameStats) -> GameStats:
        """Save or update game stats."""
        existing = await self.session.execute(
            select(GameStatsModel).where(
                GameStatsModel.game_slug == stats.game_slug,
                GameStatsModel.mode_slug == stats.mode_slug,
            )
        )
        row = existing.scalar_one_or_none()

        if row:
            row.best_score = stats.best_score
            row.times_played = stats.times_played
        else:
            row = GameStatsModel(
                game_slug=stats.game_slug,
                mode_slug=stats.mode_slug,
                best_score=stats.best_score,
                times_played=stats.times_played,
            )
            self.session.add(row)

        await self.session.commit()
        return stats

    async def list_by_game(self, game_slug: str) -> list[GameStats]:
        """List all stats for a game."""
        query = select(GameStatsModel).where(
            GameStatsModel.game_slug == game_slug,
        )
        result = await self.session.execute(query)
        rows = result.scalars().all()

        return [
            GameStats(
                game_slug=row.game_slug,
                mode_slug=row.mode_slug,
                best_score=row.best_score,
                times_played=row.times_played,
            )
            for row in rows
        ]

    async def update_score(
        self,
        game_slug: str,
        mode_slug: str,
        score: int,
    ) -> GameStats:
        """Update score for a game mode."""
        existing = await self.session.execute(
            select(GameStatsModel).where(
                GameStatsModel.game_slug == game_slug,
                GameStatsModel.mode_slug == mode_slug,
            )
        )
        row = existing.scalar_one_or_none()

        if row:
            # Update best score if new score is higher
            if score > row.best_score:
                row.best_score = score
            row.times_played += 1
        else:
            # First time playing this mode
            row = GameStatsModel(
                game_slug=game_slug,
                mode_slug=mode_slug,
                best_score=score,
                times_played=1,
            )
            self.session.add(row)

        await self.session.commit()

        return GameStats(
            game_slug=row.game_slug,
            mode_slug=row.mode_slug,
            best_score=row.best_score,
            times_played=row.times_played,
        )

    async def get_leaderboard(
        self,
        game_slug: str,
        mode_slug: str,
        limit: int = 10,
    ) -> list[GameStats]:
        """Get top scores for a game mode.
        
        Note: Currently returns only the single best score since we track
        per-player stats. Future: extend to multi-player with leaderboards.
        """
        stats = await self.get(game_slug, mode_slug)
        
        if not stats:
            return []
        
        return [stats]
