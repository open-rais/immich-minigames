"""Admin-configurable settings for Who'sThatPerson (ADMIN-FEATURE.md point #4) - see
games/settings_spec.py for the contract, services/game_settings.py for how every game's specs get
assembled into one registry and read/written."""

from games.settings_spec import SettingSpec
from games.whos_that_person.game import MAX_HIDDEN_FACES, MODE_NAMED_FACES, TOTAL_PEOPLE

SETTING_SPECS: dict[str, list[SettingSpec]] = {
    MODE_NAMED_FACES: [
        SettingSpec("total_people", TOTAL_PEOPLE, "int", 1, 500),
        SettingSpec("max_hidden_faces", MAX_HIDDEN_FACES, "int", 1, 30),
    ],
}
