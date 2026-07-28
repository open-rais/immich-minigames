"""Admin REST endpoints (ADMIN-FEATURE.md point #4) - lets an is_admin account view/edit/reset the
scoring/difficulty settings each game exposes (see services/game_settings.py's GAME_SETTING_SPECS
for what's configurable and why). Mounted under /admin/games by api/api.py. Reuses admin_api.py's
get_current_admin_user dependency rather than reimplementing the is_admin check."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from api.admin_api import get_current_admin_user
from api.deps import get_db_session
from api.dto.common import GameSettingsOut
from persistence.users import UserModel
from services.game_settings import GAME_SETTING_SPECS, GameSettingsService

router = APIRouter(prefix="/admin/games", tags=["admin"])


def get_game_settings_service(session: Annotated[Session, Depends(get_db_session)]) -> GameSettingsService:
    return GameSettingsService(session)


def _settings_out(game_type: str, mode: str, service: GameSettingsService) -> GameSettingsOut:
    return GameSettingsOut.from_specs(
        game_type, mode, service.get_specs(game_type, mode), service.get_settings(game_type, mode)
    )


def _require_known_game_mode(game_type: str, mode: str) -> None:
    if (game_type, mode) not in GAME_SETTING_SPECS:
        raise HTTPException(status_code=404, detail=f"unknown game type/mode {game_type!r}/{mode!r}")


@router.get("/settings", response_model=list[GameSettingsOut])
def list_game_settings(
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    service: Annotated[GameSettingsService, Depends(get_game_settings_service)],
) -> list[GameSettingsOut]:
    return [_settings_out(game_type, mode, service) for game_type, mode in GAME_SETTING_SPECS]


@router.put("/{game_type}/{mode}/settings", response_model=GameSettingsOut)
def update_game_settings(
    game_type: str,
    mode: str,
    body: Annotated[dict[str, float], Body()],
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    service: Annotated[GameSettingsService, Depends(get_game_settings_service)],
) -> GameSettingsOut:
    _require_known_game_mode(game_type, mode)
    service.update_settings(game_type, mode, body)
    return _settings_out(game_type, mode, service)


@router.post("/{game_type}/{mode}/settings/reset", response_model=GameSettingsOut)
def reset_game_settings(
    game_type: str,
    mode: str,
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    service: Annotated[GameSettingsService, Depends(get_game_settings_service)],
) -> GameSettingsOut:
    _require_known_game_mode(game_type, mode)
    service.reset_settings(game_type, mode)
    return _settings_out(game_type, mode, service)
