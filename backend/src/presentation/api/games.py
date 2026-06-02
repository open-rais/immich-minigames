from fastapi import APIRouter

from src.application.game_registry import get_game_registry
from pydantic import BaseModel


class GameModeResponse(BaseModel):
    slug: str
    name: str
    description: str


class GameResponse(BaseModel):
    slug: str
    name: str
    description: str
    modes: list[GameModeResponse]


router = APIRouter(prefix="/games", tags=["games"])


@router.get("", response_model=list[GameResponse])
async def list_games() -> list[GameResponse]:
    """List all available games. Game metadata is static and does not require Immich."""
    registry = get_game_registry()
    games: list[GameResponse] = []

    for game_slug in registry.list_games():
        plugin_class = registry.get(game_slug)
        plugin = plugin_class(None)  # get_game_info() is static, no provider needed
        game_info = await plugin.get_game_info()

        modes = [
            GameModeResponse(
                slug=mode.slug,
                name=mode.name,
                description=mode.description,
            )
            for mode in game_info.modes
        ]

        games.append(
            GameResponse(
                slug=game_info.slug,
                name=game_info.name,
                description=game_info.description,
                modes=modes,
            )
        )

    return games
