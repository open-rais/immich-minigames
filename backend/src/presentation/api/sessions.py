from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel

from src.application.session_service import (
    SessionService,
)
from src.infraestructure.cache.redis_client import (
    get_redis_client,
)
from src.infraestructure.cache.redis_session_repository import (
    RedisSessionRepository,
)
from src.infraestructure.immich.provider import (
    ImmichProvider,
)
from src.presentation.api.dependencies import (
    get_immich_provider,
)


class CreateSessionRequest(BaseModel):
    game_slug: str
    mode_slug: str


class SessionResponse(BaseModel):
    session_id: str
    game_slug: str
    mode_slug: str

    score: int
    streak: int
    rounds_played: int

    is_active: bool
    is_game_over: bool

    round: dict | None


class SubmitAnswerRequest(BaseModel):
    answer: str


class SubmitAnswerResponse(BaseModel):
    correct: bool
    score: int
    streak: int
    game_over: bool

    revealed: dict
    next_round: dict | None


async def get_session_service(
    immich_provider: ImmichProvider = Depends(
        get_immich_provider
    ),
) -> SessionService:
    redis_client = await get_redis_client()

    repository = RedisSessionRepository(
        redis_client
    )

    return SessionService(
        session_repository=repository,
        immich_provider=immich_provider,
    )


router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
)


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    request: CreateSessionRequest,
    service: SessionService = Depends(
        get_session_service
    ),
) -> SessionResponse:
    try:
        session, initial_round = (
            await service.create_session(
                game_slug=request.game_slug,
                mode_slug=request.mode_slug,
            )
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
        streak=session.streak,
        rounds_played=session.rounds_played,
        is_active=session.is_active,
        is_game_over=session.is_game_over,
        round=initial_round.model_dump(),
    )


@router.get(
    "/{session_id}",
)
async def get_session(
    session_id: str,
    service: SessionService = Depends(
        get_session_service
    ),
):
    session = await service.get_session(
        session_id
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return {
        "session_id": session.session_id,
        "game_slug": session.game_slug,
        "mode_slug": session.mode_slug,
        "score": session.score,
        "streak": session.streak,
        "rounds_played": session.rounds_played,
        "is_active": session.is_active,
        "is_game_over": session.is_game_over,
    }


@router.post(
    "/{session_id}/answer",
    response_model=SubmitAnswerResponse,
)
async def submit_answer(
    session_id: str,
    request: SubmitAnswerRequest,
    service: SessionService = Depends(
        get_session_service
    ),
) -> SubmitAnswerResponse:
    try:
        result = await service.submit_answer(
            session_id=session_id,
            answer=request.answer,
        )

        return SubmitAnswerResponse(
            correct=result["correct"],
            score=result["score"],
            streak=result["streak"],
            game_over=result["game_over"],
            revealed=result["revealed"],
            next_round=result.get("next_round"),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def end_session(
    session_id: str,
    service: SessionService = Depends(
        get_session_service
    ),
) -> None:
    success = await service.end_session(
        session_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    