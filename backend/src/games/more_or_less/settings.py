"""Admin-configurable settings for MoreOrLess (ADMIN-FEATURE.md point #4) - see
games/settings_spec.py for the contract, services/game_settings.py for how every game's specs get
assembled into one registry and read/written."""

from games.more_or_less.game import MODE_ALBUM_ASSETS, MODE_PERSON_ASSETS
from games.settings_spec import SettingSpec

# No scoring/difficulty knob worth exposing today for either mode - kept as explicit empty entries
# (rather than omitted) so GET /admin/games/settings still lists both of MoreOrLess's modes
# (roadmap point #f - each mode is now its own admin row/entry).
SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_PERSON_ASSETS: [],
    MODE_ALBUM_ASSETS: [],
}
