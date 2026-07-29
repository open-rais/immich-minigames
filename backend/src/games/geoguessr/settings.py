"""Admin-configurable settings for Geoguessr (ADMIN-FEATURE.md point #4) - see
games/settings_spec.py for the contract, services/game_settings.py for how every game's specs get
assembled into one registry and read/written."""

from games.geoguessr.game import (
    DECAY_KM,
    FLAT_SCORE_RADIUS_KM,
    MAX_EXTRA_ASSETS,
    MAX_SCORE,
    MODE_DISTANCE_BETWEEN_GUESS,
    TOTAL_ROUNDS,
)
from games.settings_spec import SettingSpec

SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_DISTANCE_BETWEEN_GUESS: [
        SettingSpec("total_rounds", TOTAL_ROUNDS, "int", 1, 50),
        SettingSpec("max_score", MAX_SCORE, "int", 1, 100000),
        SettingSpec("max_extra_assets", MAX_EXTRA_ASSETS, "int", 0, 20),
        SettingSpec("flat_score_radius_km", FLAT_SCORE_RADIUS_KM, "float", 0, 20000),
        SettingSpec("decay_km", DECAY_KM, "float", 0.01, 20000),
    ],
}
