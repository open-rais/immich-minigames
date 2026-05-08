from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.game_registry import get_game_registry
from src.domain.entities.game import Round
from src.infraestructure.immich.provider import ImmichProvider
from src.presentation.api.dependencies import get_immich_provider


# =============================================================================
# Schemas
# =============================================================================


class GenerateRoundRequest(BaseModel):
    """Request schema for generating a round."""
    game_slug: str
    mode_slug: str


class RoundResponse(BaseModel):
    """Response schema for a game round."""
    game_slug: str
    mode_slug: str
    question: dict
    round_id: str | None = None


class AnswerRequest(BaseModel):
    """Request schema for submitting an answer."""
    answer: str


class AnswerResponse(BaseModel):
    """Response schema for answer validation."""
    is_correct: bool
    correct_answer: str
    score: int


# =============================================================================
# Router
# =============================================================================


router = APIRouter(prefix="/rounds", tags=["rounds"])


@router.post("", response_model=RoundResponse, status_code=status.HTTP_201_CREATED)
async def generate_round(
    request: GenerateRoundRequest,
    immich_provider: ImmichProvider = Depends(get_immich_provider),
) -> RoundResponse:
    """Generate a new round for a game mode."""
    registry = get_game_registry()

    # Validate game exists
    if not registry.is_registered(request.game_slug):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game '{request.game_slug}' not found",
        )

    try:
        # Create game instance with Immich provider
        plugin_class = registry.get(request.game_slug)
        plugin = plugin_class(immich_provider)

        # Validate mode exists
        game_info = await plugin.get_game_info()
        valid_modes = [mode.slug for mode in game_info.modes]

        if request.mode_slug not in valid_modes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mode '{request.mode_slug}' not found. "
                f"Valid modes: {', '.join(valid_modes)}",
            )

        # Generate round
        round_data = await plugin.generate_round(request.mode_slug)

        return RoundResponse(
            game_slug=round_data.game_slug,
            mode_slug=round_data.mode_slug,
            question=round_data.question,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{game_slug}/{mode_slug}/answer", response_model=AnswerResponse)
async def submit_answer(
    game_slug: str,
    mode_slug: str,
    request: AnswerRequest,
    immich_provider: ImmichProvider = Depends(get_immich_provider),
) -> AnswerResponse:
    """Submit answer for a round (simple validation).
    
    Note: In a full implementation, this would validate against
    the current session's round.
    """
    registry = get_game_registry()

    # Validate game exists
    if not registry.is_registered(game_slug):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game '{game_slug}' not found",
        )

    try:
        # Create game instance
        plugin_class = registry.get(game_slug)
        plugin = plugin_class(immich_provider)

        # Generate a round to get correct answer (in real implementation,
        # this would come from session state)
        round_data = await plugin.generate_round(mode_slug)

        # Validate answer
        is_correct = await plugin.validate_answer(
            mode_slug=mode_slug,
            correct_answer=round_data.correct_answer,
            user_answer=request.answer,
        )

        # Calculate score
        score = await plugin.calculate_score(
            mode_slug=mode_slug,
            correct_answer=round_data.correct_answer,
            user_answer=request.answer,
            is_correct=is_correct,
        )

        return AnswerResponse(
            is_correct=is_correct,
            correct_answer=str(round_data.correct_answer),
            score=score,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
