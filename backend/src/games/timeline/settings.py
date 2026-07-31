"""Admin-configurable settings for Timeline - see games/settings_spec.py for the contract,
games/settings_registry.py for how every game's specs get assembled into one registry and
services/game_settings_service.py for how they're read/written."""

from games.settings_spec import CHAIN_LENGTH_SPEC, NO_REPEAT_DAYS_SPEC, SettingSpec
from games.timeline.game import MAX_CARDS, MIN_SEPARATION_DAYS, MODE_ARCADE
from games.timeline.round import TOLERANCE_DAYS

SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_ARCADE: [
        SettingSpec("tolerance_days", TOLERANCE_DAYS, "int", 0, 3650),
        SettingSpec("min_separation_days", MIN_SEPARATION_DAYS, "int", 0, 3650),
        SettingSpec("max_cards", MAX_CARDS, "int", 0, 500),  # 0 = no limit
    ],
}

# Timeline is chain-shaped like MoreOrLess (its daily build_spec pre-generates a fixed-length
# chain, so it needs chain_length) but its content is still concrete assets that shouldn't repeat
# across days (so it also needs no_repeat_days, unlike MoreOrLess) - see services/daily_settings.py
# for how this gets combined with SETTING_SPECS above.
DAILY_SETTING_SPECS: list[SettingSpec] = [CHAIN_LENGTH_SPEC, NO_REPEAT_DAYS_SPEC]
