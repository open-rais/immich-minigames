from fastapi import APIRouter

from src.presentation.api.health import router as health_router
from src.presentation.api.settings import router as settings_router
from src.presentation.api.games import router as games_router
from src.presentation.api.sessions import router as sessions_router
from src.presentation.api.stats import router as stats_router
from src.presentation.api.rounds import router as rounds_router

router = APIRouter()

router.include_router(health_router)
router.include_router(settings_router)
router.include_router(games_router)
router.include_router(sessions_router)
router.include_router(stats_router)
router.include_router(rounds_router)