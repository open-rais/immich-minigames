"""Dependency injection utilities for presentation layer."""

import redis.asyncio as redis

from src.domain.repositories.settings_repository import SettingsRepository
from src.infraestructure.db.database import SessionLocal
from src.infraestructure.db.repositories.settings_repository import (
    SQLAlchemySettingsRepository,
)
from src.infraestructure.cache.redis_client import get_redis_client
from src.infraestructure.immich.factory import create_immich_provider
from src.infraestructure.immich.provider import ImmichProvider


async def get_settings_repository() -> SettingsRepository:
    """Dependency to provide settings repository."""
    async with SessionLocal() as session:
        yield SQLAlchemySettingsRepository(session)


async def get_immich_provider() -> ImmichProvider:
    """Dependency to provide Immich provider.
    
    Fetches settings from DB and creates provider instance.
    Raises HTTPException if settings not configured.
    """
    from fastapi import HTTPException, status

    async with SessionLocal() as session:
        repo = SQLAlchemySettingsRepository(session)
        settings = await repo.get()

        if not settings:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Immich settings not configured. "
                "Please configure settings first using POST /api/v1/settings",
            )

        provider = await create_immich_provider(settings)
        return provider
