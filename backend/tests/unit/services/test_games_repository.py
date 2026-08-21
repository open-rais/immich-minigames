import uuid
from datetime import date, timedelta

from conftest import mint_invite_code

from persistence.daily import DailyChallengeModel
from persistence.games import GameModel

_MODE = "distance-between-guess"
_OTHER_MODE = "days-to-date"


def _unique_game_type() -> str:
    # daily_streaks_by_mode only ever groups by whatever string ends up in DailyChallengeModel's
    # game_type column - it doesn't need to be a real game. A fresh one per test avoids colliding
    # with daily_challenges' (challenge_date, game_type, mode) unique constraint across test
    # methods, since db_session isn't rolled back between tests (_reset_own_db in conftest.py only
    # resets once per whole test session).
    return f"test-game-{uuid.uuid4().hex[:8]}"


def _register_user(auth_service):
    unique = uuid.uuid4().hex[:8]
    return auth_service.register(
        email=f"streaks-{unique}@example.com",
        username=f"streaks-{unique}",
        full_name="Streaks Test User",
        password="correct-horse-battery-staple",
        invite_code=mint_invite_code(),
    )


def _finished_daily_game(db_session, user_id, day, game_type, mode=_MODE):
    # Get-or-create the challenge - a real (day, game_type, mode) challenge is one row shared by
    # every player of it, not one per player (see persistence/daily.py's own unique constraint),
    # so a test giving two different users the same day/game_type/mode has to reuse the same row.
    challenge = (
        db_session.query(DailyChallengeModel)
        .filter_by(challenge_date=day, game_type=game_type, mode=mode)
        .one_or_none()
    )
    if challenge is None:
        challenge = DailyChallengeModel(challenge_date=day, game_type=game_type, mode=mode, spec={}, settings={})
        db_session.add(challenge)
        db_session.flush()
    game = GameModel(user_id=user_id, game_type=game_type, mode=mode, finished=True, daily_challenge_id=challenge.id)
    db_session.add(game)
    db_session.commit()


class TestDailyStreaksByMode:
    def test_empty_user_ids_returns_empty_dict(self, game_repository):
        assert game_repository.daily_streaks_by_mode([], date.today()) == {}

    def test_three_consecutive_days_gives_a_streak_of_three(self, db_session, game_repository, auth_service):
        user = _register_user(auth_service)
        game_type = _unique_game_type()
        today = date.today()
        for offset in (2, 1, 0):
            _finished_daily_game(db_session, user.id, today - timedelta(days=offset), game_type)

        streaks = game_repository.daily_streaks_by_mode([user.id], today)
        assert streaks[(user.id, game_type, _MODE)] == 3

    def test_a_gap_breaks_the_streak(self, db_session, game_repository, auth_service):
        user = _register_user(auth_service)
        game_type = _unique_game_type()
        today = date.today()
        _finished_daily_game(db_session, user.id, today - timedelta(days=3), game_type)
        _finished_daily_game(db_session, user.id, today, game_type)

        streaks = game_repository.daily_streaks_by_mode([user.id], today)
        assert streaks[(user.id, game_type, _MODE)] == 1

    def test_as_of_yesterday_excludes_a_game_played_today(self, db_session, game_repository, auth_service):
        """The regression this exists to catch: counting through *today* (as_of=today) and
        through *yesterday* (as_of=today-1) must give different answers for the exact same
        underlying data whenever today was actually played - reusing an "as of today" streak
        count for a "does this user have anything at risk if they skip today" question would
        silently make every currently-in-progress streak read as broken."""
        user = _register_user(auth_service)
        game_type = _unique_game_type()
        today = date.today()
        yesterday = today - timedelta(days=1)
        _finished_daily_game(db_session, user.id, yesterday, game_type)
        _finished_daily_game(db_session, user.id, today, game_type)

        through_today = game_repository.daily_streaks_by_mode([user.id], today)
        through_yesterday = game_repository.daily_streaks_by_mode([user.id], yesterday)

        assert through_today[(user.id, game_type, _MODE)] == 2
        assert through_yesterday[(user.id, game_type, _MODE)] == 1

    def test_separate_modes_get_separate_streaks(self, db_session, game_repository, auth_service):
        user = _register_user(auth_service)
        game_type = _unique_game_type()
        today = date.today()
        _finished_daily_game(db_session, user.id, today, game_type, mode=_MODE)
        _finished_daily_game(db_session, user.id, today - timedelta(days=1), game_type, mode=_MODE)
        _finished_daily_game(db_session, user.id, today, game_type, mode=_OTHER_MODE)

        streaks = game_repository.daily_streaks_by_mode([user.id], today)
        assert streaks[(user.id, game_type, _MODE)] == 2
        assert streaks[(user.id, game_type, _OTHER_MODE)] == 1

    def test_separate_users_get_independent_streaks(self, db_session, game_repository, auth_service):
        user_a = _register_user(auth_service)
        user_b = _register_user(auth_service)
        game_type = _unique_game_type()
        today = date.today()
        _finished_daily_game(db_session, user_a.id, today, game_type)
        _finished_daily_game(db_session, user_a.id, today - timedelta(days=1), game_type)
        _finished_daily_game(db_session, user_b.id, today, game_type)

        streaks = game_repository.daily_streaks_by_mode([user_a.id, user_b.id], today)
        assert streaks[(user_a.id, game_type, _MODE)] == 2
        assert streaks[(user_b.id, game_type, _MODE)] == 1

    def test_a_user_with_no_games_has_no_entry(self, game_repository, auth_service):
        user = _register_user(auth_service)
        streaks = game_repository.daily_streaks_by_mode([user.id], date.today())
        assert streaks == {}
