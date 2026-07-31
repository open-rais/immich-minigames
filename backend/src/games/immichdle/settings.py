"""Admin-configurable settings for Immichdle (ADMIN-FEATURE.md point #4) - see
games/settings_spec.py for the contract, games/settings_registry.py for how every game's specs get
assembled into one registry and services/game_settings_service.py for how they're read/written."""

from games.immichdle.game import ASSET_COUNT_WEIGHT_EXPONENT, MODE_PERSON, STARTING_SCORE
from games.immichdle.round import WRONG_GUESS_PENALTY
from games.settings_spec import NO_REPEAT_DAYS_SPEC, SettingSpec

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

# Roadmap #G decisions [E]/[F] (docs/TODO/DAILY-GAMES.md §4.2) - Immichdle's target is a concrete
# named person, so its daily rotation needs a no-repeat window like every game except MoreOrLess.
DAILY_SETTING_SPECS: list[SettingSpec] = [NO_REPEAT_DAYS_SPEC]
