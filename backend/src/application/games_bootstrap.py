"""Game plugins bootstrap and initialization."""

from src.application.game_registry import get_game_registry
from src.games.more_or_less import MoreOrLessGame


def initialize_games() -> None:
    """Register all available game plugins.
    
    Called on application startup to populate the game registry.
    """
    registry = get_game_registry()
    
    # Register games - using factory since they need Immich provider
    # Actual instantiation happens at request time via dependency injection
    registry.register("more_or_less", MoreOrLessGame)
