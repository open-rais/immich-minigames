"""Admin-configurable settings for Trivium - see games/settings_spec.py for the contract,
games/settings_registry.py for how every game's specs get assembled into one registry and
services/game_settings_service.py for how they're read/written."""

from games.settings_spec import CHAIN_LENGTH_SPEC, NO_REPEAT_DAYS_SPEC, SettingSpec
from games.trivium.game import MAX_ROUNDS
from games.trivium.modes import MODE_BIRTHDAY, MODE_LOCATION, MODE_MIXED, MODE_PHOTOS
from games.trivium.round import ANSWER_TIME_SECONDS, MAX_POINTS

# Same three knobs for every mode (they all share TriviumGame/TriviumRound - see games/trivium/
# game.py's module docstring for why there's only one Game/Round pair) - defined once and reused
# rather than four structurally-identical literal lists.
_MODE_SETTING_SPECS: list[SettingSpec] = [
    SettingSpec("max_points", MAX_POINTS, "int", 1, 1000),
    # min_value=1 (not 0) - calculate_score divides by answer_time_seconds * 1000.
    SettingSpec("answer_time_seconds", ANSWER_TIME_SECONDS, "int", 1, 120),
    SettingSpec("max_rounds", MAX_ROUNDS, "int", 0, 500),  # 0 = no limit
]

SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_BIRTHDAY: _MODE_SETTING_SPECS,
    MODE_PHOTOS: _MODE_SETTING_SPECS,
    MODE_LOCATION: _MODE_SETTING_SPECS,
    MODE_MIXED: _MODE_SETTING_SPECS,
}

# Trivium is chain-shaped like MoreOrLess/Timeline (its daily build_spec pre-generates a
# fixed-length chain, so it needs chain_length) and its content is concrete people/assets that
# shouldn't repeat across days (so it also needs no_repeat_days, like Timeline but unlike
# MoreOrLess) - see services/daily_settings.py for how this gets combined with SETTING_SPECS above.
DAILY_SETTING_SPECS: list[SettingSpec] = [CHAIN_LENGTH_SPEC, NO_REPEAT_DAYS_SPEC]
