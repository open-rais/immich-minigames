"""Admin-configurable settings for Geoguessr - see games/settings_spec.py for the contract,
games/settings_registry.py for how every game's specs get assembled into one registry and
services/game_settings_service.py for how they're read/written."""

from games.geoguessr.game import MAX_EXTRA_ASSETS, MODE_DISTANCE_BETWEEN_GUESS, TOTAL_ROUNDS
from games.geoguessr.round import DECAY_KM, FLAT_SCORE_RADIUS_KM, MAX_SCORE
from games.settings_spec import NO_REPEAT_DAYS_SPEC, SettingSpec

SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_DISTANCE_BETWEEN_GUESS: [
        SettingSpec("total_rounds", TOTAL_ROUNDS, "int", 1, 50),
        SettingSpec("max_score", MAX_SCORE, "int", 1, 100000),
        SettingSpec("max_extra_assets", MAX_EXTRA_ASSETS, "int", 0, 20),
        SettingSpec("flat_score_radius_km", FLAT_SCORE_RADIUS_KM, "float", 0, 20000),
        SettingSpec("decay_km", DECAY_KM, "float", 0.01, 20000),
    ],
}

# Geoguessr's own content is concrete assets, so its daily rotation needs a no-repeat window like
# every game except MoreOrLess.
DAILY_SETTING_SPECS: list[SettingSpec] = [NO_REPEAT_DAYS_SPEC]
