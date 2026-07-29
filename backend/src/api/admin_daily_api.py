"""Admin REST endpoints for daily-game config (roadmap point #G, closes the pending roadmap #f
sub-point "cada modo tendrá una casilla 'Activar juego diario'") - lets an is_admin account
enable/disable each mode's daily rotation and edit its daily-only settings (see
services/daily_settings.py's DAILY_SETTING_SPECS for what's configurable and why). Mounted under
/admin/daily by api/api.py. Mirrors api/admin_games_api.py's shape closely - same
get_current_admin_user dependency, same list/update/reset routes - just against the daily config
instead of the normal one."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.admin_api import get_current_admin_user
from api.deps import get_db_session
from api.dto.admin import DailySettingsOut, UpdateDailySettingsIn
from persistence.users import UserModel
from services.daily_settings import DAILY_SETTING_SPECS, DailySettingsService

router = APIRouter(prefix="/admin/daily", tags=["admin"])


def get_daily_settings_service(session: Annotated[Session, Depends(get_db_session)]) -> DailySettingsService:
    return DailySettingsService(session)


def _settings_out(game_type: str, mode: str, service: DailySettingsService) -> DailySettingsOut:
    enabled, values = service.get_config(game_type, mode)
    return DailySettingsOut.from_specs(game_type, mode, enabled, service.get_specs(game_type, mode), values)


def _require_known_game_mode(game_type: str, mode: str) -> None:
    if (game_type, mode) not in DAILY_SETTING_SPECS:
        raise HTTPException(status_code=404, detail=f"unknown game type/mode {game_type!r}/{mode!r}")


@router.get("/settings", response_model=list[DailySettingsOut])
def list_daily_settings(
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    service: Annotated[DailySettingsService, Depends(get_daily_settings_service)],
) -> list[DailySettingsOut]:
    return [_settings_out(game_type, mode, service) for game_type, mode in DAILY_SETTING_SPECS]


@router.put("/{game_type}/{mode}", response_model=DailySettingsOut)
def update_daily_settings(
    game_type: str,
    mode: str,
    body: UpdateDailySettingsIn,
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    service: Annotated[DailySettingsService, Depends(get_daily_settings_service)],
) -> DailySettingsOut:
    _require_known_game_mode(game_type, mode)
    service.update_settings(game_type, mode, enabled=body.enabled, values=body.values)
    return _settings_out(game_type, mode, service)


@router.post("/{game_type}/{mode}/reset", response_model=DailySettingsOut)
def reset_daily_settings(
    game_type: str,
    mode: str,
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    service: Annotated[DailySettingsService, Depends(get_daily_settings_service)],
) -> DailySettingsOut:
    _require_known_game_mode(game_type, mode)
    service.reset_settings(game_type, mode)
    return _settings_out(game_type, mode, service)
