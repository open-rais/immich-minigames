"""Contract-only module (no logic) - the shape of one admin-editable game setting
(ADMIN-FEATURE.md point #4). Lives in games/ (not services/) so each <game>/settings.py can
declare its own SETTING_SPECS without games/ depending on services/ - see
docs/TODO/DECOUPLING.md's import-direction rule (`services.game_settings` -> `games.<j>.settings`
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
