"""Admin-editable per-(game_type, mode) daily configuration: whether that mode is in the daily
rotation at all (the "Activar juego diario" checkbox), plus its daily-only setting overrides (see
persistence/daily.py's DailyConfigModel).

Mirrors services/game_settings_service.py closely (same SettingSpec dataclass, same
get/update/reset-settings shape) with two differences: every (game_type, mode) here starts from
games/settings_registry.py's GAME_SETTING_SPECS as a base (a daily game plays with the same knobs
a normal game does, just possibly different values) plus that game's own extra daily-only spec(s)
(each game's own `settings.py::DAILY_SETTING_SPECS` - this module never decides *which* game needs
`chain_length` vs `no_repeat_days`, only assembles what each game already declared); and there's an
`enabled` flag alongside the values, which `reset_settings` deliberately leaves untouched (only the
value overrides reset to defaults)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr.settings import DAILY_SETTING_SPECS as DATEGUESSR_DAILY_SPECS
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr.settings import DAILY_SETTING_SPECS as GEOGUESSR_DAILY_SPECS
from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle.settings import DAILY_SETTING_SPECS as IMMICHDLE_DAILY_SPECS
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less.settings import DAILY_SETTING_SPECS as MORE_OR_LESS_DAILY_SPECS
from games.settings_registry import GAME_SETTING_SPECS
from games.settings_spec import SettingSpec
from games.timeline import GAME_TYPE as TIMELINE_TYPE
from games.timeline.settings import DAILY_SETTING_SPECS as TIMELINE_DAILY_SPECS
from games.whos_that_person import GAME_TYPE as WHOS_THAT_PERSON_TYPE
from games.whos_that_person.settings import DAILY_SETTING_SPECS as WHOS_THAT_PERSON_DAILY_SPECS
from persistence.daily import DailyConfigModel
from services.game_settings_service import (
    InvalidGameSettingValueError,  # noqa: F401 (re-exported - same error type this service raises)
    UnknownGameSettingError,
    validate_setting_value,
)

# Each game's own settings.py declares its extra daily-only spec(s) (games/settings_spec.py's
# NO_REPEAT_DAYS_SPEC/CHAIN_LENGTH_SPEC) - this module only assembles them onto GAME_SETTING_SPECS
# below, it never decides per-mode which one a game needs (that decision lives with the game
# itself). A game_type absent here (Trivium, until it gets a daily.py of its own) simply gets no
# extra specs - not every registered game has daily support yet.
_EXTRA_DAILY_SPECS_BY_GAME_TYPE: dict[str, list[SettingSpec]] = {
    GEOGUESSR_TYPE: GEOGUESSR_DAILY_SPECS,
    DATEGUESSR_TYPE: DATEGUESSR_DAILY_SPECS,
    IMMICHDLE_TYPE: IMMICHDLE_DAILY_SPECS,
    WHOS_THAT_PERSON_TYPE: WHOS_THAT_PERSON_DAILY_SPECS,
    MORE_OR_LESS_TYPE: MORE_OR_LESS_DAILY_SPECS,
    TIMELINE_TYPE: TIMELINE_DAILY_SPECS,
}

DAILY_SETTING_SPECS: dict[tuple[str, str], list[SettingSpec]] = {
    (game_type, mode): [*base, *_EXTRA_DAILY_SPECS_BY_GAME_TYPE.get(game_type, [])]
    for (game_type, mode), base in GAME_SETTING_SPECS.items()
}


class DailySettingsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_specs(self, game_type: str, mode: str) -> list[SettingSpec]:
        return DAILY_SETTING_SPECS.get((game_type, mode), [])

    def is_enabled(self, game_type: str, mode: str) -> bool:
        row = self._session.get(DailyConfigModel, (game_type, mode))
        return row.enabled if row is not None else False

    def list_enabled(self) -> list[tuple[str, str]]:
        """Every (game_type, mode) currently in the daily rotation - `GET /daily`'s menu listing
        (services/games_service.py's get_daily_status) iterates this rather than every known mode,
        so a disabled mode simply doesn't show up (existing in-progress games stay playable by id
        regardless, only the menu card disappears)."""
        rows = self._session.execute(
            select(DailyConfigModel.game_type, DailyConfigModel.mode).where(DailyConfigModel.enabled.is_(True))
        ).all()
        return [(game_type, mode) for game_type, mode in rows]

    def get_settings(self, game_type: str, mode: str) -> dict[str, float]:
        """Effective daily-only values for this (game_type, mode) - every spec's default,
        overridden by whatever's persisted. Read fresh every time a challenge is generated (see
        services/daily_challenge_service.py), same "always live, never cached" rationale as
        GameSettingsService.get_settings - the *challenge* is what freezes these, not this call."""
        defaults = {spec.key: spec.default for spec in self.get_specs(game_type, mode)}
        row = self._session.get(DailyConfigModel, (game_type, mode))
        if row is None:
            return defaults
        return {**defaults, **row.values}

    def get_config(self, game_type: str, mode: str) -> tuple[bool, dict[str, float]]:
        return self.is_enabled(game_type, mode), self.get_settings(game_type, mode)

    def update_settings(
        self, game_type: str, mode: str, *, enabled: bool | None = None, values: dict[str, float] | None = None
    ) -> tuple[bool, dict[str, float]]:
        if values:
            specs = {spec.key: spec for spec in self.get_specs(game_type, mode)}
            for key, value in values.items():
                spec = specs.get(key)
                if spec is None:
                    raise UnknownGameSettingError(f"{game_type}/{mode} has no daily setting {key!r}")
                validate_setting_value(spec, value)

        row = self._session.get(DailyConfigModel, (game_type, mode))
        if row is None:
            row = DailyConfigModel(game_type=game_type, mode=mode, enabled=False, values={})
            self._session.add(row)
        if enabled is not None:
            row.enabled = enabled
        if values:
            row.values = {**row.values, **values}
        self._session.commit()
        return self.get_config(game_type, mode)

    def reset_settings(self, game_type: str, mode: str) -> tuple[bool, dict[str, float]]:
        """Clears value overrides back to defaults - `enabled` is untouched, so the row itself is
        never deleted outright (unlike GameSettingsService.reset_settings, which has no other
        field worth preserving)."""
        row = self._session.get(DailyConfigModel, (game_type, mode))
        if row is not None:
            row.values = {}
            self._session.commit()
        return self.get_config(game_type, mode)
