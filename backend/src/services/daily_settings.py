"""Roadmap #G (daily games) - admin-editable per-(game_type, mode) daily configuration: whether
that mode is in the daily rotation at all (the "Activar juego diario" checkbox from roadmap #f),
plus its daily-only setting overrides (see persistence/daily.py's DailyConfigModel).

Mirrors services/game_settings.py closely (same SettingSpec dataclass, same
get/update/reset-settings shape) with two differences: every (game_type, mode) here starts from
that same module's GAME_SETTING_SPECS as a base (a daily game plays with the same knobs a normal
game does, just possibly different values) plus one extra daily-only spec; and there's an
`enabled` flag alongside the values, which `reset_settings` deliberately leaves untouched (only the
value overrides reset to defaults - see docs/TODO/DAILY-GAMES.md §4.6, "enabled no se resetea")."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import MODE_ALBUM_ASSETS, MODE_PERSON_ASSETS
from games.timeline import GAME_TYPE as TIMELINE_TYPE
from games.timeline import MODE_ARCADE as TIMELINE_MODE_ARCADE
from persistence.daily import DailyConfigModel
from services.game_settings import (
    GAME_SETTING_SPECS,
    InvalidGameSettingValueError,  # noqa: F401 (re-exported - same error type this service raises)
    SettingSpec,
    UnknownGameSettingError,
    validate_setting_value,
)

# Roadmap #G decisions [E]/[F] (docs/TODO/DAILY-GAMES.md §4.2) - every mode except MoreOrLess needs
# a no-repeat window (assets/persons excluded from the last N days' challenges); MoreOrLess instead
# gets a cap on its pre-generated candidate chain, since it has no "asset/person" content to avoid
# repeating within a single day (the roadmap: "ahí solo debe ser otra seed"). Timeline is the first
# mode that needs *both* (docs/TODO/TIMELINE.md decision [G]): its own content is concrete assets
# (so it still needs no_repeat_days like every other game), but it's also chain-shaped like
# MoreOrLess (so it needs chain_length too, to cap how many cards get pre-generated). Composed by
# set membership rather than an if/else so a mode can land in either, both, or neither.
_NO_REPEAT_DAYS_SPEC = SettingSpec("no_repeat_days", 30, "int", 0, 365)
_CHAIN_LENGTH_SPEC = SettingSpec("chain_length", 100, "int", 10, 1000)
_MORE_OR_LESS_MODES = {(MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS), (MORE_OR_LESS_TYPE, MODE_ALBUM_ASSETS)}
_CHAIN_MODES = _MORE_OR_LESS_MODES | {(TIMELINE_TYPE, TIMELINE_MODE_ARCADE)}
_NO_REPEAT_MODES = set(GAME_SETTING_SPECS) - _MORE_OR_LESS_MODES


def _daily_specs_for(game_type: str, mode: str) -> list[SettingSpec]:
    base = GAME_SETTING_SPECS.get((game_type, mode), [])
    extras: list[SettingSpec] = []
    if (game_type, mode) in _CHAIN_MODES:
        extras.append(_CHAIN_LENGTH_SPEC)
    if (game_type, mode) in _NO_REPEAT_MODES:
        extras.append(_NO_REPEAT_DAYS_SPEC)
    return [*base, *extras]


DAILY_SETTING_SPECS: dict[tuple[str, str], list[SettingSpec]] = {
    key: _daily_specs_for(*key) for key in GAME_SETTING_SPECS
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
        so a disabled mode simply doesn't show up (docs/TODO/DAILY-GAMES.md §5's "Challenge de un
        modo deshabilitado a mitad del día" - existing in-progress games stay playable by id
        regardless, only the menu card disappears)."""
        rows = self._session.execute(
            select(DailyConfigModel.game_type, DailyConfigModel.mode).where(DailyConfigModel.enabled.is_(True))
        ).all()
        return [(game_type, mode) for game_type, mode in rows]

    def get_settings(self, game_type: str, mode: str) -> dict[str, float]:
        """Effective daily-only values for this (game_type, mode) - every spec's default,
        overridden by whatever's persisted. Read fresh every time a challenge is generated (see
        services/daily_service.py), same "always live, never cached" rationale as
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
        """Clears value overrides back to defaults - `enabled` is untouched (§4.6's "enabled no se
        resetea"), so the row itself is never deleted outright (unlike
        GameSettingsService.reset_settings, which has no other field worth preserving)."""
        row = self._session.get(DailyConfigModel, (game_type, mode))
        if row is not None:
            row.values = {}
            self._session.commit()
        return self.get_config(game_type, mode)
