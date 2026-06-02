from collections.abc import Callable

from src.domain.entities.game_plugin import GamePlugin


class GameRegistry:
    """Simple plugin registry."""

    def __init__(self) -> None:
        self._plugins: dict[str, Callable[..., GamePlugin]] = {}

    def register(
        self,
        game_slug: str,
        factory: Callable[..., GamePlugin],
    ) -> None:
        if game_slug in self._plugins:
            raise ValueError(
                f"Game '{game_slug}' is already registered"
            )

        self._plugins[game_slug] = factory

    def get(
        self,
        game_slug: str,
    ) -> Callable[..., GamePlugin]:
        if game_slug not in self._plugins:
            raise KeyError(
                f"Game '{game_slug}' is not registered"
            )

        return self._plugins[game_slug]

    def list_games(self) -> list[str]:
        return list(self._plugins.keys())

    def is_registered(
        self,
        game_slug: str,
    ) -> bool:
        return game_slug in self._plugins


_game_registry: GameRegistry | None = None


def get_game_registry() -> GameRegistry:
    global _game_registry

    if _game_registry is None:
        _game_registry = GameRegistry()

    return _game_registry
