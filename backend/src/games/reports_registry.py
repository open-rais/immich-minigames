"""Assembles every game's own report-exclusion mapping (each game's own
games/<game>/reports.py::REPORT_EXCLUSIONS, keyed by mode) into one (game_type, mode)-keyed
registry - which open-report reasons exclude a candidate is decided per-game, in that game's own
reports.py (see games/report_spec.py for the shared ReportReason/ReportEntity vocabulary). Mirrors
games/settings_registry.py's shape exactly. services/reports_service.py::ReportsService.filter_for
is the only reader.
"""

from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr.reports import REPORT_EXCLUSIONS as DATEGUESSR_REPORT_EXCLUSIONS
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr.reports import REPORT_EXCLUSIONS as GEOGUESSR_REPORT_EXCLUSIONS
from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle.reports import REPORT_EXCLUSIONS as IMMICHDLE_REPORT_EXCLUSIONS
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less.reports import REPORT_EXCLUSIONS as MORE_OR_LESS_REPORT_EXCLUSIONS
from games.report_spec import ReportReason
from games.timeline import GAME_TYPE as TIMELINE_TYPE
from games.timeline.reports import REPORT_EXCLUSIONS as TIMELINE_REPORT_EXCLUSIONS
from games.trivium import GAME_TYPE as TRIVIUM_TYPE
from games.trivium.reports import REPORT_EXCLUSIONS as TRIVIUM_REPORT_EXCLUSIONS
from games.whos_that_person import GAME_TYPE as WHOS_THAT_PERSON_TYPE
from games.whos_that_person.reports import REPORT_EXCLUSIONS as WHOS_THAT_PERSON_REPORT_EXCLUSIONS


def _flatten(
    game_type: str, exclusions_by_mode: dict[str, frozenset[ReportReason]]
) -> dict[tuple[str, str], frozenset[ReportReason]]:
    return {(game_type, mode): reasons for mode, reasons in exclusions_by_mode.items()}


REPORT_EXCLUSIONS: dict[tuple[str, str], frozenset[ReportReason]] = {
    **_flatten(GEOGUESSR_TYPE, GEOGUESSR_REPORT_EXCLUSIONS),
    **_flatten(DATEGUESSR_TYPE, DATEGUESSR_REPORT_EXCLUSIONS),
    **_flatten(IMMICHDLE_TYPE, IMMICHDLE_REPORT_EXCLUSIONS),
    **_flatten(WHOS_THAT_PERSON_TYPE, WHOS_THAT_PERSON_REPORT_EXCLUSIONS),
    **_flatten(MORE_OR_LESS_TYPE, MORE_OR_LESS_REPORT_EXCLUSIONS),
    **_flatten(TIMELINE_TYPE, TIMELINE_REPORT_EXCLUSIONS),
    **_flatten(TRIVIUM_TYPE, TRIVIUM_REPORT_EXCLUSIONS),
}
