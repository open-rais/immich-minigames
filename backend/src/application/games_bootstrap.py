"""Game plugins bootstrap and initialization."""

from src.application.game_registry import (
    get_game_registry,
)

from src.games.more_or_less.plugin import (
    MoreOrLessPlugin,
)


def initialize_games() -> None:
    """Register all available game plugins."""

    registry = get_game_registry()

    registry.register(
        "more_or_less",
        MoreOrLessPlugin,
    )
