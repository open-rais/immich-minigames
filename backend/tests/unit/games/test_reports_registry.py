from games.registry import GAMES
from games.reports_registry import REPORT_EXCLUSIONS


class TestReportExclusionsRegistry:
    def test_every_registered_game_mode_declares_its_report_exclusions(self):
        missing = [key for key in GAMES if key not in REPORT_EXCLUSIONS]

        assert missing == [], f"(game_type, mode) missing from games.reports_registry.REPORT_EXCLUSIONS: {missing}"
