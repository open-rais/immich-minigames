import uuid
from datetime import date, datetime

from conftest import mint_invite_code

from services.notifications.runner import _mark_delivered, _seconds_until_midnight


def _register_user(auth_service):
    unique = uuid.uuid4().hex[:8]
    return auth_service.register(
        email=f"runner-{unique}@example.com",
        username=f"runner-{unique}",
        full_name="Runner Test User",
        password="correct-horse-battery-staple",
        invite_code=mint_invite_code(),
    )


class TestSecondsUntilMidnight:
    def test_at_exactly_midnight_a_full_day_remains(self):
        assert _seconds_until_midnight(datetime(2026, 1, 5, 0, 0, 0)) == 24 * 60 * 60

    def test_one_second_before_midnight(self):
        assert _seconds_until_midnight(datetime(2026, 1, 5, 23, 59, 59)) == 1

    def test_at_9pm_three_hours_remain(self):
        assert _seconds_until_midnight(datetime(2026, 1, 5, 21, 0, 0)) == 3 * 60 * 60

    def test_never_negative(self):
        assert _seconds_until_midnight(datetime(2026, 1, 5, 23, 59, 59, 999999)) >= 0


class TestMarkDelivered:
    def test_the_first_delivery_of_the_day_returns_true(self, db_session, auth_service):
        user = _register_user(auth_service)
        assert _mark_delivered(db_session, user.id, "birthdays", date(2026, 1, 5)) is True

    def test_a_second_delivery_of_the_same_kind_and_day_returns_false(self, db_session, auth_service):
        user = _register_user(auth_service)
        today = date(2026, 1, 5)
        _mark_delivered(db_session, user.id, "birthdays", today)
        assert _mark_delivered(db_session, user.id, "birthdays", today) is False

    def test_a_different_kind_the_same_day_is_independent(self, db_session, auth_service):
        user = _register_user(auth_service)
        today = date(2026, 1, 5)
        _mark_delivered(db_session, user.id, "birthdays", today)
        assert _mark_delivered(db_session, user.id, "album_anniversary", today) is True

    def test_the_same_kind_a_different_day_is_independent(self, db_session, auth_service):
        user = _register_user(auth_service)
        _mark_delivered(db_session, user.id, "birthdays", date(2026, 1, 5))
        assert _mark_delivered(db_session, user.id, "birthdays", date(2026, 1, 6)) is True
