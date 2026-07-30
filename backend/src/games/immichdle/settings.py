"""Admin-configurable settings for Immichdle (ADMIN-FEATURE.md point #4) - see
games/settings_spec.py for the contract, services/game_settings.py for how every game's specs get
assembled into one registry and read/written."""

from games.immichdle.game import ASSET_COUNT_WEIGHT_EXPONENT, MODE_PERSON, STARTING_SCORE, WRONG_GUESS_PENALTY
from games.settings_spec import SettingSpec

SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_PERSON: [
        SettingSpec("starting_score", STARTING_SCORE, "int", 1, 10000),
        SettingSpec("wrong_guess_penalty", WRONG_GUESS_PENALTY, "int", 0, 1000),
        # Not a scoring/difficulty knob like the two above but a target-selection fairness one
        # (games/immichdle/game.py's ASSET_COUNT_WEIGHT_EXPONENT) - min/max are the exponent's
        # actual valid range (0=uniform, 1=fully proportional to photo count), not the
        # generous-multiplier safety rail this module's other max_values use.
        SettingSpec("asset_count_weight", ASSET_COUNT_WEIGHT_EXPONENT, "float", 0, 1),
    ],
}
