from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.core.constants import API_PREFIX
from src.presentation.api.router import router as api_router
from src.application.games_bootstrap import initialize_games


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize game plugins on startup
initialize_games()

app.include_router(
    api_router,
    prefix=API_PREFIX,
)