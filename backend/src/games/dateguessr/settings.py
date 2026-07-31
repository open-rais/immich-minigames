"""Admin-configurable settings for Dateguessr (ADMIN-FEATURE.md point #4) - see
games/settings_spec.py for the contract, games/settings_registry.py for how every game's specs get
assembled into one registry and services/game_settings_service.py for how they're read/written."""

from games.dateguessr.game import MAX_EXTRA_ASSETS, MODE_DAYS_TO_DATE, TOTAL_ROUNDS
from games.dateguessr.round import DECAY_DAYS, FLAT_SCORE_DAYS, MAX_SCORE
from games.settings_spec import NO_REPEAT_DAYS_SPEC, SettingSpec

SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_DAYS_TO_DATE: [
        SettingSpec("total_rounds", TOTAL_ROUNDS, "int", 1, 50),
        SettingSpec("max_score", MAX_SCORE, "int", 1, 100000),
        SettingSpec("max_extra_assets", MAX_EXTRA_ASSETS, "int", 0, 20),
        SettingSpec("flat_score_days", FLAT_SCORE_DAYS, "int", 0, 36500),
        SettingSpec("decay_days", DECAY_DAYS, "float", 0.01, 36500),
    ],
}

# Roadmap #G decisions [E]/[F] (docs/TODO/DAILY-GAMES.md §4.2) - Dateguessr's own content is
# concrete assets, so its daily rotation needs a no-repeat window like every game except MoreOrLess.
DAILY_SETTING_SPECS: list[SettingSpec] = [NO_REPEAT_DAYS_SPEC]
