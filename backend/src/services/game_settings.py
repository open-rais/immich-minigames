"""Admin feature (ADMIN-FEATURE.md point #4) - assembles every game's own admin-editable settings
(each game's own `games/<game>/settings.py::SETTING_SPECS`, keyed by mode) into one
(game_type, mode)-keyed registry, plus the service that reads/writes per-game_type overrides
(persistence/game_settings.py). Which knobs are exposed at all is decided per-game, in that game's
own settings.py (see games/settings_spec.py for the shared SettingSpec/ValueType contract) - this
module never makes that call itself, only assembles what each game already declared.
"""

import math

from sqlalchemy.orm import Session

from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr.settings import SETTING_SPECS as DATEGUESSR_SETTING_SPECS
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr.settings import SETTING_SPECS as GEOGUESSR_SETTING_SPECS
from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle.settings import SETTING_SPECS as IMMICHDLE_SETTING_SPECS
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less.settings import SETTING_SPECS as MORE_OR_LESS_SETTING_SPECS
from games.settings_spec import SettingSpec, ValueType  # noqa: F401 (ValueType re-exported for callers)
from games.timeline import GAME_TYPE as TIMELINE_TYPE
from games.timeline.settings import SETTING_SPECS as TIMELINE_SETTING_SPECS
from games.whos_that_person import GAME_TYPE as WHOS_THAT_PERSON_TYPE
from games.whos_that_person.settings import SETTING_SPECS as WHOS_THAT_PERSON_SETTING_SPECS
from persistence.game_settings import GameSettingsModel


def _flatten(game_type: str, specs_by_mode: dict[str, list[SettingSpec]]) -> dict[tuple[str, str], list[SettingSpec]]:
    return {(game_type, mode): specs for mode, specs in specs_by_mode.items()}


GAME_SETTING_SPECS: dict[tuple[str, str], list[SettingSpec]] = {
    **_flatten(GEOGUESSR_TYPE, GEOGUESSR_SETTING_SPECS),
    **_flatten(DATEGUESSR_TYPE, DATEGUESSR_SETTING_SPECS),
    **_flatten(IMMICHDLE_TYPE, IMMICHDLE_SETTING_SPECS),
    **_flatten(WHOS_THAT_PERSON_TYPE, WHOS_THAT_PERSON_SETTING_SPECS),
    **_flatten(MORE_OR_LESS_TYPE, MORE_OR_LESS_SETTING_SPECS),
    **_flatten(TIMELINE_TYPE, TIMELINE_SETTING_SPECS),
}


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
        (services/games_service.py's _game_kwargs) - deliberately re-read live every time rather
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
