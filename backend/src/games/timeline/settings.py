"""Admin-configurable settings for Timeline (ADMIN-FEATURE.md point #4) - see games/settings_spec.py
for the contract, services/game_settings.py for how every game's specs get assembled into one
registry and read/written."""

from games.settings_spec import SettingSpec
from games.timeline.game import MAX_CARDS, MIN_SEPARATION_DAYS, MODE_ARCADE, TOLERANCE_DAYS

SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_ARCADE: [
        SettingSpec("tolerance_days", TOLERANCE_DAYS, "int", 0, 3650),
        SettingSpec("min_separation_days", MIN_SEPARATION_DAYS, "int", 0, 3650),
        SettingSpec("max_cards", MAX_CARDS, "int", 0, 500),  # 0 = no limit
    ],
}
