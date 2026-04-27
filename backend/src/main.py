from fastapi import FastAPI

from src.config import settings
from src.core.constants import API_PREFIX
from src.presentation.api.router import router as api_router


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

app.include_router(
    api_router,
    prefix=API_PREFIX,
)