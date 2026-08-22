from datetime import datetime

from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr import MODE_DAYS_TO_DATE
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS
from games.timeline import GAME_TYPE as TIMELINE_TYPE
from games.timeline import MODE_ARCADE
from services.notifications.schedule import active_kinds_for_tick, decide_daily_notification

_GEO = (GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS)  # earlier in games/registry.py's order
_DATE = (DATEGUESSR_TYPE, MODE_DAYS_TO_DATE)
_TIMELINE = (TIMELINE_TYPE, MODE_ARCADE)  # later in games/registry.py's order


class TestActiveKindsForTick:
    def test_exactly_at_slot_start_is_active(self):
        assert active_kinds_for_tick(datetime(2026, 1, 5, 10, 0, 0)) == ["daily_available"]

    def test_inside_the_grace_window_is_active(self):
        assert active_kinds_for_tick(datetime(2026, 1, 5, 10, 45, 0)) == ["daily_available"]

    def test_at_the_grace_window_boundary_is_not_active(self):
        # 60 minutes after 10:00 exactly - the window is a half-open [start, start+60min).
        assert active_kinds_for_tick(datetime(2026, 1, 5, 11, 0, 0)) == []

    def test_one_minute_before_the_slot_is_not_active(self):
        assert active_kinds_for_tick(datetime(2026, 1, 5, 9, 59, 0)) == []

    def test_a_time_with_no_active_slot_returns_nothing(self):
        assert active_kinds_for_tick(datetime(2026, 1, 5, 16, 30, 0)) == []

    def test_the_21_00_slot_is_independent_of_the_others(self):
        assert active_kinds_for_tick(datetime(2026, 1, 5, 21, 10, 0)) == ["daily_reminder"]


class TestDecideDailyNotification:
    def test_no_enabled_modes_sends_nothing(self):
        assert decide_daily_notification([], [], {}) is None

    def test_no_active_streak_anywhere_sends_daily_available(self):
        decision = decide_daily_notification([_GEO, _DATE], [_GEO, _DATE], {_GEO: 0, _DATE: 0})
        assert decision is not None
        assert decision.kind == "daily_available"

    def test_active_streak_but_everything_already_played_sends_nothing(self):
        decision = decide_daily_notification([_GEO], [], {_GEO: 5})
        assert decision is None

    def test_active_streak_elsewhere_but_not_in_the_unplayed_set_sends_the_generic_reminder(self):
        # racha(GEO) > 0 but GEO is already finished (not in unfinished_modes) - only DATE (no
        # streak) is left to play, so R is empty even though the user does have an active streak.
        decision = decide_daily_notification([_GEO, _DATE], [_DATE], {_GEO: 5, _DATE: 0})
        assert decision is not None
        assert decision.kind == "daily_reminder"
        assert decision.variant == "generic"

    def test_a_single_at_risk_streak_sends_streak_at_risk_with_its_details(self):
        decision = decide_daily_notification([_GEO], [_GEO], {_GEO: 7})
        assert decision.kind == "daily_reminder"
        assert decision.variant == "streak_at_risk"
        assert decision.game_type == GEOGUESSR_TYPE
        assert decision.streak == 7

    def test_the_larger_of_two_at_risk_streaks_wins(self):
        decision = decide_daily_notification([_GEO, _DATE], [_GEO, _DATE], {_GEO: 3, _DATE: 9})
        assert decision.game_type == DATEGUESSR_TYPE
        assert decision.streak == 9

    def test_a_tie_is_broken_by_registry_declaration_order(self):
        # _GEO comes before _TIMELINE in games/registry.py's GAMES dict - same streak value on
        # both must deterministically pick _GEO, not whichever happens to iterate last.
        decision = decide_daily_notification([_GEO, _TIMELINE], [_GEO, _TIMELINE], {_GEO: 4, _TIMELINE: 4})
        assert decision.game_type == GEOGUESSR_TYPE

        decision_reversed = decide_daily_notification(
            [_TIMELINE, _GEO], [_TIMELINE, _GEO], {_TIMELINE: 4, _GEO: 4}
        )
        assert decision_reversed.game_type == GEOGUESSR_TYPE
