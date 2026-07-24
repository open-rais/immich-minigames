"""Admin feature (ADMIN-FEATURE.md point #4) - registry of which of each game's currently-
hardcoded constants (games/*.py) are exposed as admin-editable settings, plus the service that
reads/writes per-game_type overrides (persistence/game_settings.py). Scope deliberately limited to
knobs that affect visible scoring/difficulty (confirmed with the project owner) - internal
sampling/variety parameters (e.g. asset_rounds.py's _CANDIDATE_SAMPLE_SIZE) stay pure module
constants, never exposed here. Geoguessr and Dateguessr get independent entries below even though
they share the same asset_rounds.py defaults today (also confirmed with the project owner) - each
game_type is looked up/persisted separately.
"""

import math
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from games.asset_rounds import MAX_EXTRA_ASSETS, MAX_SCORE, TOTAL_ROUNDS
from games.dateguessr import DECAY_DAYS, FLAT_SCORE_DAYS
from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.geoguessr import DECAY_KM, FLAT_SCORE_RADIUS_KM
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle import ASSET_COUNT_WEIGHT_EXPONENT, STARTING_SCORE, WRONG_GUESS_PENALTY
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.whos_that_person import GAME_TYPE as WHOS_THAT_PERSON_TYPE
from games.whos_that_person import MAX_HIDDEN_FACES, TOTAL_PEOPLE
from persistence.game_settings import GameSettingsModel

ValueType = Literal["int", "float"]


@dataclass(frozen=True)
class SettingSpec:
    key: str
    default: float
    value_type: ValueType
    min_value: float
    # Safety rail, not game design (docs/TODO/CODE-REVIEW.md #7) - total_rounds/total_people
    # directly govern has_next_round(), so an unbounded value means the game never ends and keeps
    # firing new-round queries; max_score unbounded permanently pollutes leaderboards. Values below
    # are generous (10x-200x each default) but finite, confirmed with the project owner.
    max_value: float


GAME_SETTING_SPECS: dict[str, list[SettingSpec]] = {
    GEOGUESSR_TYPE: [
        SettingSpec("total_rounds", TOTAL_ROUNDS, "int", 1, 50),
        SettingSpec("max_score", MAX_SCORE, "int", 1, 100000),
        SettingSpec("max_extra_assets", MAX_EXTRA_ASSETS, "int", 0, 20),
        SettingSpec("flat_score_radius_km", FLAT_SCORE_RADIUS_KM, "float", 0, 20000),
        SettingSpec("decay_km", DECAY_KM, "float", 0.01, 20000),
    ],
    DATEGUESSR_TYPE: [
        SettingSpec("total_rounds", TOTAL_ROUNDS, "int", 1, 50),
        SettingSpec("max_score", MAX_SCORE, "int", 1, 100000),
        SettingSpec("max_extra_assets", MAX_EXTRA_ASSETS, "int", 0, 20),
        SettingSpec("flat_score_days", FLAT_SCORE_DAYS, "int", 0, 36500),
        SettingSpec("decay_days", DECAY_DAYS, "float", 0.01, 36500),
    ],
    IMMICHDLE_TYPE: [
        SettingSpec("starting_score", STARTING_SCORE, "int", 1, 10000),
        SettingSpec("wrong_guess_penalty", WRONG_GUESS_PENALTY, "int", 0, 1000),
        # Not a scoring/difficulty knob like the two above but a target-selection fairness one
        # (games/immichdle.py's ASSET_COUNT_WEIGHT_EXPONENT) - min/max are the exponent's actual
        # valid range (0=uniform, 1=fully proportional to photo count), not the generous-multiplier
        # safety rail this class's other max_values use.
        SettingSpec("asset_count_weight", ASSET_COUNT_WEIGHT_EXPONENT, "float", 0, 1),
    ],
    WHOS_THAT_PERSON_TYPE: [
        SettingSpec("total_people", TOTAL_PEOPLE, "int", 1, 500),
        SettingSpec("max_hidden_faces", MAX_HIDDEN_FACES, "int", 1, 30),
    ],
    # No scoring/difficulty knob worth exposing today (see module docstring) - kept as an explicit
    # empty entry (rather than omitted) so GET /admin/games/settings still lists MoreOrLess.
    MORE_OR_LESS_TYPE: [],
}


class UnknownGameSettingError(Exception):
    pass


class InvalidGameSettingValueError(Exception):
    pass


class GameSettingsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_specs(self, game_type: str) -> list[SettingSpec]:
        return GAME_SETTING_SPECS.get(game_type, [])

    def get_settings(self, game_type: str) -> dict[str, float]:
        """Effective values for this game_type - every spec's default, overridden by whatever's
        persisted. Called by GamesService on every game start/load (services/games_service.py's
        _game_kwargs) - deliberately re-read live every time rather than cached, so an admin
        change takes effect on the very next round played, not just new games."""
        defaults = {spec.key: spec.default for spec in self.get_specs(game_type)}
        row = self._session.get(GameSettingsModel, game_type)
        if row is None:
            return defaults
        return {**defaults, **row.values}

    def update_settings(self, game_type: str, values: dict[str, float]) -> dict[str, float]:
        specs = {spec.key: spec for spec in self.get_specs(game_type)}
        for key, value in values.items():
            spec = specs.get(key)
            if spec is None:
                raise UnknownGameSettingError(f"{game_type} has no setting {key!r}")
            # Checked first, before any arithmetic on value - Python's JSON parser accepts the
            # NaN/Infinity literals, and NaN compares False to everything (so it'd sail past
            # min/max below) while int(nan) raises a raw ValueError instead of the typed error here.
            if not math.isfinite(value):
                raise InvalidGameSettingValueError(f"{key} must be a finite number")
            if value < spec.min_value:
                raise InvalidGameSettingValueError(f"{key} must be >= {spec.min_value}")
            if value > spec.max_value:
                raise InvalidGameSettingValueError(f"{key} must be <= {spec.max_value}")
            if spec.value_type == "int" and value != int(value):
                raise InvalidGameSettingValueError(f"{key} must be a whole number")

        row = self._session.get(GameSettingsModel, game_type)
        if row is None:
            row = GameSettingsModel(game_type=game_type, values={})
            self._session.add(row)
        row.values = {**row.values, **values}
        self._session.commit()
        return self.get_settings(game_type)

    def reset_settings(self, game_type: str) -> dict[str, float]:
        row = self._session.get(GameSettingsModel, game_type)
        if row is not None:
            self._session.delete(row)
            self._session.commit()
        return self.get_settings(game_type)
