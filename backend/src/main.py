"""App entrypoint. Initializes the own-schema DB tables and mounts the API router."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.api import router
from persistance.games import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Immich Minigames", lifespan=lifespan)
app.include_router(router)
