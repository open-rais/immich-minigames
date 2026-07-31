"""Admin-configurable settings for MoreOrLess (ADMIN-FEATURE.md point #4) - see
games/settings_spec.py for the contract, games/settings_registry.py for how every game's specs get
assembled into one registry and services/game_settings_service.py for how they're read/written."""

from games.more_or_less.game import MODE_ALBUM_ASSETS, MODE_PERSON_ASSETS
from games.settings_spec import CHAIN_LENGTH_SPEC, SettingSpec

# No scoring/difficulty knob worth exposing today for either mode - kept as explicit empty entries
# (rather than omitted) so GET /admin/games/settings still lists both of MoreOrLess's modes
# (roadmap point #f - each mode is now its own admin row/entry).
SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_PERSON_ASSETS: [],
    MODE_ALBUM_ASSETS: [],
}

# Roadmap #G decisions [E]/[F] (docs/TODO/DAILY-GAMES.md §4.2) - MoreOrLess's daily build_spec
# pre-generates a fixed-length chain instead of avoiding repeats across days (it has no
# "asset/person" content of its own to avoid repeating within a single day - "ahí solo debe ser
# otra seed"), so it needs chain_length and not no_repeat_days, unlike every other game.
DAILY_SETTING_SPECS: list[SettingSpec] = [CHAIN_LENGTH_SPEC]
