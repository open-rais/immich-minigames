from fastapi import FastAPI

from src.config import settings
from src.core.constants import API_PREFIX
from src.presentation.api.router import router as api_router
from src.application.games_bootstrap import initialize_games


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

# Initialize game plugins on startup
initialize_games()

app.include_router(
    api_router,
    prefix=API_PREFIX,
)