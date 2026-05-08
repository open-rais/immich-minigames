from typing import Type

from src.domain.entities.game import Game
from src.domain.entities.game_plugin import GamePlugin


class GameRegistry:
    """Registry for game plugins using Factory pattern.
    
    Manages registration and instantiation of game plugins.
    Supports dynamic plugin loading and querying.
    """

    def __init__(self) -> None:
        """Initialize empty plugin registry."""
        self._plugins: dict[str, Type[GamePlugin]] = {}

    def register(self, game_slug: str, plugin_class: Type[GamePlugin]) -> None:
        """Register a game plugin.
        
        Args:
            game_slug: Unique identifier for the game
            plugin_class: Plugin class (uninstantiated)
            
        Raises:
            ValueError: If game_slug is already registered
        """
        if game_slug in self._plugins:
            raise ValueError(f"Game '{game_slug}' is already registered")
        
        self._plugins[game_slug] = plugin_class

    def get(self, game_slug: str) -> Type[GamePlugin]:
        """Get a registered plugin class.
        
        Args:
            game_slug: The game slug
            
        Returns:
            The plugin class
            
        Raises:
            KeyError: If game_slug is not registered
        """
        if game_slug not in self._plugins:
            raise KeyError(f"Game '{game_slug}' is not registered")
        
        return self._plugins[game_slug]

    def create_instance(self, game_slug: str) -> GamePlugin:
        """Create an instance of a registered plugin.
        
        Args:
            game_slug: The game slug
            
        Returns:
            Instantiated plugin
            
        Raises:
            KeyError: If game_slug is not registered
        """
        plugin_class = self.get(game_slug)
        return plugin_class()

    def list_games(self) -> list[str]:
        """List all registered game slugs.
        
        Returns:
            List of registered game slugs
        """
        return list(self._plugins.keys())

    def is_registered(self, game_slug: str) -> bool:
        """Check if a game is registered.
        
        Args:
            game_slug: The game slug
            
        Returns:
            True if registered, False otherwise
        """
        return game_slug in self._plugins


# Global registry instance
_game_registry: GameRegistry | None = None


def get_game_registry() -> GameRegistry:
    """Get or create the global game registry singleton."""
    global _game_registry
    if _game_registry is None:
        _game_registry = GameRegistry()
    return _game_registry
