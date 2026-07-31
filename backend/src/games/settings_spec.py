"""Contract-only module (no logic) - the shape of one admin-editable game setting
(ADMIN-FEATURE.md point #4). Lives in games/ (not services/) so each <game>/settings.py can
declare its own SETTING_SPECS without games/ depending on services/ - see
docs/TODO/DECOUPLING.md's import-direction rule (`games.settings_registry` -> `games.<j>.settings`
-> `games.settings_spec`, never the other way)."""

from dataclasses import dataclass
from typing import Literal

ValueType = Literal["int", "float"]


@dataclass(frozen=True)
class SettingSpec:
    key: str
    default: float
    value_type: ValueType
    min_value: float
    # Safety rail, not game design (docs/TODO/CODE-REVIEW.md #7) - a total_rounds/total_people spec
    # directly governs has_next_round(), so an unbounded value means the game never ends and keeps
    # firing new-round queries; an unbounded max_score permanently pollutes leaderboards. Each
    # game's own settings.py picks a generous-but-finite value, confirmed with the project owner.
    max_value: float


# Roadmap #G decisions [E]/[F] (docs/TODO/DAILY-GAMES.md §4.2) - shared by every game's own
# `settings.py::DAILY_SETTING_SPECS` that needs one of these two daily-only knobs, so the same
# (key, default, bounds) isn't redefined per game. `no_repeat_days` is for a mode whose content is
# concrete assets/persons that shouldn't repeat across days; `chain_length` is for a mode that
# pre-generates a fixed-length chain instead (MoreOrLess, Timeline) - see each game's own
# settings.py for which one(s) it declares.
NO_REPEAT_DAYS_SPEC = SettingSpec("no_repeat_days", 30, "int", 0, 365)
CHAIN_LENGTH_SPEC = SettingSpec("chain_length", 100, "int", 10, 1000)
