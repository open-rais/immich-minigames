from fastapi import APIRouter, Depends

from src.application.game_registry import get_game_registry
from src.infraestructure.immich.provider import ImmichProvider
from src.presentation.api.dependencies import get_immich_provider
from pydantic import BaseModel


# =============================================================================
# Schemas
# =============================================================================


class GameModeResponse(BaseModel):
    """Response schema for game mode."""
    slug: str
    name: str
    description: str


class GameResponse(BaseModel):
    """Response schema for game info."""
    slug: str
    name: str
    description: str
    modes: list[GameModeResponse]


# =============================================================================
# Router
# =============================================================================


router = APIRouter(prefix="/games", tags=["games"])


@router.get("", response_model=list[GameResponse])
async def list_games(
    immich_provider: ImmichProvider = Depends(get_immich_provider),
) -> list[GameResponse]:
    """List all available games with their modes."""
    registry = get_game_registry()
    games: list[GameResponse] = []
    
    for game_slug in registry.list_games():
        # Create game instance with Immich provider
        plugin_class = registry.get(game_slug)
        plugin = plugin_class(immich_provider)
        
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
