"""Admin-configurable settings for Immichdle - see games/settings_spec.py for the contract,
games/registry.py for how every game's specs get assembled into one registry and
services/game_settings_service.py for how they're read/written."""

from games.immichdle.albumdle import ASSET_COUNT_WEIGHT_EXPONENT as ALBUM_ASSET_COUNT_WEIGHT_EXPONENT
from games.immichdle.game import MODE_ALBUM, MODE_PERSON, STARTING_SCORE, WRONG_GUESS_PENALTY
from games.immichdle.persondle import ASSET_COUNT_WEIGHT_EXPONENT as PERSON_ASSET_COUNT_WEIGHT_EXPONENT
from games.settings_spec import NO_REPEAT_DAYS_SPEC, SettingSpec

# min/max on the asset_count_weight entries below are the exponent's actual valid range (0=uniform,
# 1=fully proportional to asset count), not the generous-multiplier safety rail this module's other
# max_values use. Independent constants per mode (like Geoguessr/Dateguessr's own copies) rather
# than one shared default, even though both happen to default to 0.2 today.
SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_PERSON: [
        SettingSpec("starting_score", STARTING_SCORE, "int", 1, 10000),
        SettingSpec("wrong_guess_penalty", WRONG_GUESS_PENALTY, "int", 0, 1000),
        SettingSpec("asset_count_weight", PERSON_ASSET_COUNT_WEIGHT_EXPONENT, "float", 0, 1),
        SettingSpec("require_birth_date", 0, "bool", 0, 1),
    ],
    MODE_ALBUM: [
        SettingSpec("starting_score", STARTING_SCORE, "int", 1, 10000),
        SettingSpec("wrong_guess_penalty", WRONG_GUESS_PENALTY, "int", 0, 1000),
        SettingSpec("asset_count_weight", ALBUM_ASSET_COUNT_WEIGHT_EXPONENT, "float", 0, 1),
    ],
}

# Both modes' targets are a concrete named entity, so both need a no-repeat window like every game
# except MoreOrLess.
DAILY_SETTING_SPECS: list[SettingSpec] = [NO_REPEAT_DAYS_SPEC]
