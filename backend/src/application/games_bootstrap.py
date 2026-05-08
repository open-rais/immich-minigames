"""Game plugins bootstrap and initialization."""

from src.application.game_registry import get_game_registry

# Import future game plugins here as they're implemented
# from src.games.more_or_less import MoreOrLessGame
# from src.games.geoguessr import GeoguessrGame


def initialize_games() -> None:
    """Register all available game plugins.
    
    Called on application startup to populate the game registry.
    """
    registry = get_game_registry()
    
    # Register games here as they're implemented
    # registry.register("more_or_less", MoreOrLessGame)
    # registry.register("geoguessr", GeoguessrGame)
    
    # Placeholder for testing
    # When no games are registered, the registry will return an empty list
