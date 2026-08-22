"""Which open-report reasons exclude a candidate from Dateguessr's live sampling, per mode - see
games/reports_registry.py for how this assembles with every other game's, and
services/reports_service.py for the wrapper that actually applies it."""

from games.dateguessr.game import MODE_DAYS_TO_DATE
from games.report_spec import ReportReason

REPORT_EXCLUSIONS: dict[str, frozenset[ReportReason]] = {
    MODE_DAYS_TO_DATE: frozenset({ReportReason.ASSET_DATE}),
}
