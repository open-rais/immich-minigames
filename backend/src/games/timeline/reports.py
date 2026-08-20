"""Which open-report reasons exclude a candidate from Timeline's live sampling, per mode - see
games/reports_registry.py for how this assembles with every other game's, and
services/reports_service.py for the wrapper that actually applies it."""

from games.report_spec import ReportReason
from games.timeline.game import MODE_ARCADE

REPORT_EXCLUSIONS: dict[str, frozenset[ReportReason]] = {
    MODE_ARCADE: frozenset({ReportReason.ASSET_DATE}),
}
