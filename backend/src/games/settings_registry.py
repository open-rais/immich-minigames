"""Assembles every game's own admin-editable settings (each game's own
`games/<game>/settings.py::SETTING_SPECS`, keyed by mode) into one
(game_type, mode)-keyed registry. Which knobs are exposed at all is decided per-game, in that
game's own settings.py (see games/settings_spec.py for the shared SettingSpec/ValueType contract) -
this module never makes that call itself, only assembles what each game already declared. Pure
knowledge (no persistence/business logic), same rationale as games/registry.py - see
services/game_settings_service.py for the service that reads/writes per-game_type overrides.
"""

from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr.settings import SETTING_SPECS as DATEGUESSR_SETTING_SPECS
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr.settings import SETTING_SPECS as GEOGUESSR_SETTING_SPECS
from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle.settings import SETTING_SPECS as IMMICHDLE_SETTING_SPECS
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less.settings import SETTING_SPECS as MORE_OR_LESS_SETTING_SPECS
from games.settings_spec import SettingSpec
from games.timeline import GAME_TYPE as TIMELINE_TYPE
from games.timeline.settings import SETTING_SPECS as TIMELINE_SETTING_SPECS
from games.whos_that_person import GAME_TYPE as WHOS_THAT_PERSON_TYPE
from games.whos_that_person.settings import SETTING_SPECS as WHOS_THAT_PERSON_SETTING_SPECS


def _flatten(game_type: str, specs_by_mode: dict[str, list[SettingSpec]]) -> dict[tuple[str, str], list[SettingSpec]]:
    return {(game_type, mode): specs for mode, specs in specs_by_mode.items()}


GAME_SETTING_SPECS: dict[tuple[str, str], list[SettingSpec]] = {
    **_flatten(GEOGUESSR_TYPE, GEOGUESSR_SETTING_SPECS),
    **_flatten(DATEGUESSR_TYPE, DATEGUESSR_SETTING_SPECS),
    **_flatten(IMMICHDLE_TYPE, IMMICHDLE_SETTING_SPECS),
    **_flatten(WHOS_THAT_PERSON_TYPE, WHOS_THAT_PERSON_SETTING_SPECS),
    **_flatten(MORE_OR_LESS_TYPE, MORE_OR_LESS_SETTING_SPECS),
    **_flatten(TIMELINE_TYPE, TIMELINE_SETTING_SPECS),
}
