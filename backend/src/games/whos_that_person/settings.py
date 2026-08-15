"""Admin-configurable settings for Who'sThatPerson - see games/settings_spec.py for the contract,
games/settings_registry.py for how every game's specs get assembled into one registry and
services/game_settings_service.py for how they're read/written."""

from games.settings_spec import NO_REPEAT_DAYS_SPEC, SettingSpec
from games.whos_that_person.game import MAX_HIDDEN_FACES, MODE_NAMED_FACES, TOTAL_PEOPLE

SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_NAMED_FACES: [
        SettingSpec("total_people", TOTAL_PEOPLE, "int", 1, 500),
        SettingSpec("max_hidden_faces", MAX_HIDDEN_FACES, "int", 1, 30),
        SettingSpec("streak_scoring", 0, "int", 0, 1),
    ],
}

# Who'sThatPerson's own content is concrete assets, so its daily rotation needs a no-repeat window
# like every game except MoreOrLess.
DAILY_SETTING_SPECS: list[SettingSpec] = [NO_REPEAT_DAYS_SPEC]
