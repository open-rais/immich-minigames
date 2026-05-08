from pydantic import BaseModel, HttpUrl
from fastapi import APIRouter, Depends, HTTPException, status
import httpx

from src.domain.entities.settings import Settings
from src.infraestructure.db.database import SessionLocal
from src.infraestructure.db.repositories.settings_repository import (
    SQLAlchemySettingsRepository,
)


# =============================================================================
# Schemas
# =============================================================================


class SettingsRequest(BaseModel):
    """Request schema for settings."""
    immich_url: HttpUrl
    immich_api_key: str

    class Config:
        json_schema_extra = {
            "example": {
                "immich_url": "http://immich.example.com",
                "immich_api_key": "abc123def456",
            }
        }


class SettingsResponse(BaseModel):
    """Response schema for settings."""
    immich_url: str
    immich_api_key: str

    class Config:
        json_schema_extra = {
            "example": {
                "immich_url": "http://immich.example.com",
                "immich_api_key": "abc123def456",
            }
        }


class TestConnectionResponse(BaseModel):
    """Response schema for test connection."""
    success: bool
    message: str


# =============================================================================
# Dependencies
# =============================================================================


async def get_settings_repository() -> SQLAlchemySettingsRepository:
    """Dependency to provide settings repository."""
    async with SessionLocal() as session:
        yield SQLAlchemySettingsRepository(session)


# =============================================================================
# Router
# =============================================================================


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(
    repository: SQLAlchemySettingsRepository = Depends(get_settings_repository),
) -> SettingsResponse:
    """Get current Immich settings."""
    settings = await repository.get()

    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Settings not found. Please configure Immich connection first.",
        )

    return SettingsResponse(
        immich_url=settings.immich_url,
        immich_api_key=settings.immich_api_key,
    )


@router.post("", response_model=SettingsResponse, status_code=status.HTTP_201_CREATED)
async def save_settings(
    request: SettingsRequest,
    repository: SQLAlchemySettingsRepository = Depends(get_settings_repository),
) -> SettingsResponse:
    """Save or update Immich settings."""
    settings = Settings(
        immich_url=str(request.immich_url),
        immich_api_key=request.immich_api_key,
    )

    saved_settings = await repository.save(settings)

    return SettingsResponse(
        immich_url=saved_settings.immich_url,
        immich_api_key=saved_settings.immich_api_key,
    )


@router.post("/test", response_model=TestConnectionResponse)
async def test_connection(
    repository: SQLAlchemySettingsRepository = Depends(get_settings_repository),
) -> TestConnectionResponse:
    """Test connection to Immich server."""
    settings = await repository.get()

    if not settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Settings not configured. Please save settings first.",
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.immich_url}/api/health",
                headers={"x-api-key": settings.immich_api_key},
                timeout=10.0,
            )

            if response.status_code == 200:
                return TestConnectionResponse(
                    success=True,
                    message="Successfully connected to Immich server",
                )
            else:
                return TestConnectionResponse(
                    success=False,
                    message=f"Immich returned status code {response.status_code}",
                )

    except httpx.ConnectError:
        return TestConnectionResponse(
            success=False,
            message="Could not connect to Immich server. Check URL and network.",
        )
    except httpx.TimeoutException:
        return TestConnectionResponse(
            success=False,
            message="Connection to Immich server timed out.",
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Error testing connection: {str(e)}",
        )
