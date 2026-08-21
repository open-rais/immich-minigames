"""Admin-configurable settings for Trivium - see games/settings_spec.py for the contract,
games/settings_registry.py for how every game's specs get assembled into one registry and
services/game_settings_service.py for how they're read/written."""

from games.settings_spec import SettingSpec
from games.trivium.game import MAX_ROUNDS
from games.trivium.modes import MODE_BIRTHDAY
from games.trivium.round import ANSWER_TIME_SECONDS, MAX_POINTS

SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_BIRTHDAY: [
        SettingSpec("max_points", MAX_POINTS, "int", 1, 1000),
        # min_value=1 (not 0) - calculate_score divides by answer_time_seconds * 1000.
        SettingSpec("answer_time_seconds", ANSWER_TIME_SECONDS, "int", 1, 120),
        SettingSpec("max_rounds", MAX_ROUNDS, "int", 0, 500),  # 0 = no limit
    ],
}
