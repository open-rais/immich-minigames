"""Admin-configurable settings for Dateguessr (ADMIN-FEATURE.md point #4) - see
games/settings_spec.py for the contract, services/game_settings.py for how every game's specs get
assembled into one registry and read/written."""

from games.dateguessr.game import (
    DECAY_DAYS,
    FLAT_SCORE_DAYS,
    MAX_EXTRA_ASSETS,
    MAX_SCORE,
    MODE_DAYS_TO_DATE,
    TOTAL_ROUNDS,
)
from games.settings_spec import SettingSpec

SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_DAYS_TO_DATE: [
        SettingSpec("total_rounds", TOTAL_ROUNDS, "int", 1, 50),
        SettingSpec("max_score", MAX_SCORE, "int", 1, 100000),
        SettingSpec("max_extra_assets", MAX_EXTRA_ASSETS, "int", 0, 20),
        SettingSpec("flat_score_days", FLAT_SCORE_DAYS, "int", 0, 36500),
        SettingSpec("decay_days", DECAY_DAYS, "float", 0.01, 36500),
    ],
}
