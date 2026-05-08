from abc import ABC, abstractmethod

from src.domain.entities.game_stats import GameStats


class GameStatsRepository(ABC):
    """Repository interface for managing game statistics."""

    @abstractmethod
    async def get(self, game_slug: str, mode_slug: str) -> GameStats | None:
        """Get stats for a game mode.
        
        Args:
            game_slug: The game identifier
            mode_slug: The game mode identifier
            
        Returns:
            GameStats if found, None otherwise
        """
        pass

    @abstractmethod
    async def save(self, stats: GameStats) -> GameStats:
        """Save or update game stats.
        
        Args:
            stats: GameStats object to save
            
        Returns:
            Saved GameStats
        """
        pass

    @abstractmethod
    async def list_by_game(self, game_slug: str) -> list[GameStats]:
        """List all stats for a game (all modes).
        
        Args:
            game_slug: The game identifier
            
        Returns:
            List of GameStats for all modes
        """
        pass

    @abstractmethod
    async def update_score(
        self,
        game_slug: str,
        mode_slug: str,
        score: int,
    ) -> GameStats:
        """Update score for a game mode.
        
        Updates best_score if new score is higher and increments times_played.
        
        Args:
            game_slug: The game identifier
            mode_slug: The game mode identifier
            score: The score achieved
            
        Returns:
            Updated GameStats
        """
        pass

    @abstractmethod
    async def get_leaderboard(
        self,
        game_slug: str,
        mode_slug: str,
        limit: int = 10,
    ) -> list[GameStats]:
        """Get top scores for a game mode.
        
        Args:
            game_slug: The game identifier
            mode_slug: The game mode identifier
            limit: Maximum number of results
            
        Returns:
            List of top GameStats
        """
        pass
