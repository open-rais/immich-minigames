from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.infraestructure.db.database import SessionLocal
from src.infraestructure.db.repositories.game_stats_repository import (
    SQLAlchemyGameStatsRepository,
)


# =============================================================================
# Schemas
# =============================================================================


class GameStatsResponse(BaseModel):
    """Response schema for game stats."""
    game_slug: str
    mode_slug: str
    best_score: int
    times_played: int

    class Config:
        json_schema_extra = {
            "example": {
                "game_slug": "more_or_less",
                "mode_slug": "person-items",
                "best_score": 450,
                "times_played": 12,
            }
        }


class UpdateScoreRequest(BaseModel):
    """Request schema for updating score."""
    score: int

    class Config:
        json_schema_extra = {
            "example": {
                "score": 350,
            }
        }


# =============================================================================
# Dependencies
# =============================================================================


async def get_game_stats_repository() -> SQLAlchemyGameStatsRepository:
    """Dependency to provide game stats repository."""
    async with SessionLocal() as session:
        yield SQLAlchemyGameStatsRepository(session)


# =============================================================================
# Router
# =============================================================================


router = APIRouter(prefix="/stats", tags=["stats"])


@router.get(
    "/{game_slug}/{mode_slug}",
    response_model=GameStatsResponse,
)
async def get_game_stats(
    game_slug: str,
    mode_slug: str,
    repository: SQLAlchemyGameStatsRepository = Depends(
        get_game_stats_repository
    ),
) -> GameStatsResponse:
    """Get stats for a game mode."""
    stats = await repository.get(game_slug, mode_slug)

    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stats found for {game_slug}/{mode_slug}",
        )

    return GameStatsResponse(
        game_slug=stats.game_slug,
        mode_slug=stats.mode_slug,
        best_score=stats.best_score,
        times_played=stats.times_played,
    )


@router.get(
    "/{game_slug}",
    response_model=list[GameStatsResponse],
)
async def list_game_stats(
    game_slug: str,
    repository: SQLAlchemyGameStatsRepository = Depends(
        get_game_stats_repository
    ),
) -> list[GameStatsResponse]:
    """Get all stats for a game (all modes)."""
    stats_list = await repository.list_by_game(game_slug)

    return [
        GameStatsResponse(
            game_slug=stats.game_slug,
            mode_slug=stats.mode_slug,
            best_score=stats.best_score,
            times_played=stats.times_played,
        )
        for stats in stats_list
    ]


@router.post(
    "/{game_slug}/{mode_slug}",
    response_model=GameStatsResponse,
)
async def update_score(
    game_slug: str,
    mode_slug: str,
    request: UpdateScoreRequest,
    repository: SQLAlchemyGameStatsRepository = Depends(
        get_game_stats_repository
    ),
) -> GameStatsResponse:
    """Update score for a game mode.
    
    Updates best_score if new score is higher.
    Always increments times_played.
    """
    stats = await repository.update_score(
        game_slug=game_slug,
        mode_slug=mode_slug,
        score=request.score,
    )

    return GameStatsResponse(
        game_slug=stats.game_slug,
        mode_slug=stats.mode_slug,
        best_score=stats.best_score,
        times_played=stats.times_played,
    )


@router.get(
    "/{game_slug}/{mode_slug}/leaderboard",
    response_model=list[GameStatsResponse],
)
async def get_leaderboard(
    game_slug: str,
    mode_slug: str,
    limit: int = 10,
    repository: SQLAlchemyGameStatsRepository = Depends(
        get_game_stats_repository
    ),
) -> list[GameStatsResponse]:
    """Get leaderboard for a game mode."""
    stats_list = await repository.get_leaderboard(
        game_slug=game_slug,
        mode_slug=mode_slug,
        limit=limit,
    )

    return [
        GameStatsResponse(
            game_slug=stats.game_slug,
            mode_slug=stats.mode_slug,
            best_score=stats.best_score,
            times_played=stats.times_played,
        )
        for stats in stats_list
    ]
