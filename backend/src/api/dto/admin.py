"""Admin-editable game settings DTOs - both the normal per-game_type ones (ADMIN-FEATURE.md point
#4, see services/game_settings.py) and the daily-only ones (roadmap point #G, see
services/daily_settings.py), which share the same GameSettingOut shape."""

from typing import Literal

from pydantic import BaseModel

from services.game_settings import SettingSpec


class GameSettingOut(BaseModel):
    key: str
    value: float
    default: float
    value_type: Literal["int", "float"]
    min_value: float
    max_value: float


class GameSettingsOut(BaseModel):
    game_type: str
    mode: str
    settings: list[GameSettingOut]

    @classmethod
    def from_specs(
        cls, game_type: str, mode: str, specs: list[SettingSpec], values: dict[str, float]
    ) -> "GameSettingsOut":
        return cls(
            game_type=game_type,
            mode=mode,
            settings=[
                GameSettingOut(
                    key=spec.key,
                    value=values[spec.key],
                    default=spec.default,
                    value_type=spec.value_type,
                    min_value=spec.min_value,
                    max_value=spec.max_value,
                )
                for spec in specs
            ],
        )


class DailySettingsOut(BaseModel):
    game_type: str
    mode: str
    # The "Activar juego diario" checkbox from roadmap #f - whether this mode is offered in the
    # daily rotation at all.
    enabled: bool
    settings: list[GameSettingOut]

    @classmethod
    def from_specs(
        cls, game_type: str, mode: str, enabled: bool, specs: list[SettingSpec], values: dict[str, float]
    ) -> "DailySettingsOut":
        return cls(
            game_type=game_type,
            mode=mode,
            enabled=enabled,
            settings=[
                GameSettingOut(
                    key=spec.key,
                    value=values[spec.key],
                    default=spec.default,
                    value_type=spec.value_type,
                    min_value=spec.min_value,
                    max_value=spec.max_value,
                )
                for spec in specs
            ],
        )


class UpdateDailySettingsIn(BaseModel):
    # PATCH semantics - omit a field to leave it unchanged (mirrors auth_schemas.py's
    # UpdateProfileIn), so toggling "enabled" from the admin UI doesn't require also restating
    # every setting value, and saving settings doesn't require also restating "enabled".
    enabled: bool | None = None
    values: dict[str, float] | None = None
