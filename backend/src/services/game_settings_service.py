"""Reads/writes per-(game_type, mode) admin overrides of the settings each game declared
(games/settings_registry.py's GAME_SETTING_SPECS), persisted in persistence/game_settings.py."""

import math

from sqlalchemy.orm import Session

from games.settings_registry import GAME_SETTING_SPECS
from games.settings_spec import SettingSpec, ValueType  # noqa: F401 (ValueType re-exported for callers)
from persistence.game_settings import GameSettingsModel


class UnknownGameSettingError(Exception):
    pass


class InvalidGameSettingValueError(Exception):
    pass


def validate_setting_value(spec: SettingSpec, value: float) -> None:
    """Shared by GameSettingsService.update_settings and DailySettingsService.update_settings
    (services/daily_settings.py) - same SettingSpec shape, same admin-input validation rules."""
    # Checked first, before any arithmetic on value - Python's JSON parser accepts the
    # NaN/Infinity literals, and NaN compares False to everything (so it'd sail past min/max
    # below) while int(nan) raises a raw ValueError instead of the typed error here.
    if not math.isfinite(value):
        raise InvalidGameSettingValueError(f"{spec.key} must be a finite number")
    if value < spec.min_value:
        raise InvalidGameSettingValueError(f"{spec.key} must be >= {spec.min_value}")
    if value > spec.max_value:
        raise InvalidGameSettingValueError(f"{spec.key} must be <= {spec.max_value}")
    if spec.value_type == "int" and value != int(value):
        raise InvalidGameSettingValueError(f"{spec.key} must be a whole number")


class GameSettingsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_specs(self, game_type: str, mode: str) -> list[SettingSpec]:
        return GAME_SETTING_SPECS.get((game_type, mode), [])

    def get_settings(self, game_type: str, mode: str) -> dict[str, float]:
        """Effective values for this (game_type, mode) - every spec's default, overridden by
        whatever's persisted. Called by GamesService on every game start/load
        (services/games_service.py's _game_kwargs), deliberately re-read live every time rather
        than cached, so an admin change takes effect on the very next round played, not just new
        games."""
        defaults = {spec.key: spec.default for spec in self.get_specs(game_type, mode)}
        row = self._session.get(GameSettingsModel, (game_type, mode))
        if row is None:
            return defaults
        return {**defaults, **row.values}

    def update_settings(self, game_type: str, mode: str, values: dict[str, float]) -> dict[str, float]:
        specs = {spec.key: spec for spec in self.get_specs(game_type, mode)}
        for key, value in values.items():
            spec = specs.get(key)
            if spec is None:
                raise UnknownGameSettingError(f"{game_type}/{mode} has no setting {key!r}")
            validate_setting_value(spec, value)

        row = self._session.get(GameSettingsModel, (game_type, mode))
        if row is None:
            row = GameSettingsModel(game_type=game_type, mode=mode, values={})
            self._session.add(row)
        row.values = {**row.values, **values}
        self._session.commit()
        return self.get_settings(game_type, mode)

    def reset_settings(self, game_type: str, mode: str) -> dict[str, float]:
        row = self._session.get(GameSettingsModel, (game_type, mode))
        if row is not None:
            self._session.delete(row)
            self._session.commit()
        return self.get_settings(game_type, mode)
