"""Which open-report reasons exclude a candidate from Geoguessr's live sampling, per mode - see
games/reports_registry.py for how this assembles with every other game's, and
services/reports_service.py for the wrapper that actually applies it."""

from games.geoguessr.game import MODE_DISTANCE_BETWEEN_GUESS
from games.report_spec import ReportReason

REPORT_EXCLUSIONS: dict[str, frozenset[ReportReason]] = {
    # Not ASSET_DATE, even though the reveal now shows the date too - the answer here is the
    # location, so a bad date doesn't invalidate the round.
    MODE_DISTANCE_BETWEEN_GUESS: frozenset({ReportReason.ASSET_LOCATION}),
}
