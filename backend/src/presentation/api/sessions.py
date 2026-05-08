from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.session_service import SessionService
from src.infraestructure.cache.redis_client import get_redis_client
from src.infraestructure.cache.redis_session_repository import RedisSessionRepository


# =============================================================================
# Schemas
# =============================================================================


class CreateSessionRequest(BaseModel):
    """Request schema for creating a session."""
    game_slug: str
    mode_slug: str

    class Config:
        json_schema_extra = {
            "example": {
                "game_slug": "more_or_less",
                "mode_slug": "person-items",
            }
        }


class SessionResponse(BaseModel):
    """Response schema for session."""
    session_id: str
    game_slug: str
    mode_slug: str
    score: int
    rounds_played: int
    is_active: bool

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "game_slug": "more_or_less",
                "mode_slug": "person-items",
                "score": 100,
                "rounds_played": 5,
                "is_active": True,
            }
        }


# =============================================================================
# Dependencies
# =============================================================================


async def get_session_service() -> SessionService:
    """Dependency to provide session service."""
    redis_client = await get_redis_client()
    repository = RedisSessionRepository(redis_client)
    return SessionService(repository)


# =============================================================================
# Router
# =============================================================================


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Create a new game session."""
    try:
        session = await service.create_session(
            game_slug=request.game_slug,
            mode_slug=request.mode_slug,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return SessionResponse(
        session_id=session.session_id,
        game_slug=session.game_slug,
        mode_slug=session.mode_slug,
        score=session.score,
        rounds_played=session.rounds_played,
        is_active=session.is_active,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Get a session by ID."""
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or has expired",
        )

    return SessionResponse(
        session_id=session.session_id,
        game_slug=session.game_slug,
        mode_slug=session.mode_slug,
        score=session.score,
        rounds_played=session.rounds_played,
        is_active=session.is_active,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> None:
    """End a session."""
    success = await service.end_session(session_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
