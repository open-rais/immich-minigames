"""Roadmap #G, phase F5 - GamesService.get_daily_leaderboard. Integration tests against the real
dev Immich DB (see conftest.py's module docstring)."""

import itertools
import uuid
from datetime import date, timedelta

import pytest
from conftest import mint_invite_code

from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle import MODE_PERSON
from persistence.daily import DailyConfigModel
from persistence.games import GameModel
from services.games_service import UnsupportedGameError

_date_counter = itertools.count()
_BASE_DATE = date(2040, 1, 1)


def _next_date() -> date:
    return _BASE_DATE + timedelta(days=next(_date_counter) * 1000)


@pytest.fixture(autouse=True)
def _clean_daily_configs(db_session):
    def _clear():
        db_session.query(DailyConfigModel).filter(DailyConfigModel.game_type == IMMICHDLE_TYPE).delete()
        db_session.commit()

    _clear()
    yield
    _clear()


def _register(auth_service):
    unique = uuid.uuid4().hex[:8]
    return auth_service.register(
        email=f"user-{unique}@example.com",
        username=f"user-{unique}",
        full_name="Test User",
        password="correct-horse-battery-staple",
        invite_code=mint_invite_code(),
    )


class TestGetDailyLeaderboard:
    def test_unsupported_mode_raises(self, games_service):
        with pytest.raises(UnsupportedGameError):
            games_service.get_daily_leaderboard(IMMICHDLE_TYPE, "not-a-real-mode", _next_date())

    def test_a_date_with_no_challenge_returns_empty(self, games_service):
        assert games_service.get_daily_leaderboard(IMMICHDLE_TYPE, MODE_PERSON, _next_date()) == []

    def test_scores_finished_games_of_that_challenge(
        self, games_service, daily_settings_service, db_session, auth_service
    ):
        daily_settings_service.update_settings(IMMICHDLE_TYPE, MODE_PERSON, enabled=True)
        d = _next_date()
        alice = _register(auth_service)
        bob = _register(auth_service)

        alice_game = games_service.create_daily_game(
            game_type=IMMICHDLE_TYPE, mode=MODE_PERSON, user_id=alice.id, today=d
        )
        bob_game = games_service.create_daily_game(game_type=IMMICHDLE_TYPE, mode=MODE_PERSON, user_id=bob.id, today=d)
        db_session.get(GameModel, alice_game.id).finished = True
        db_session.get(GameModel, alice_game.id).score = 90
        db_session.get(GameModel, bob_game.id).finished = True
        db_session.get(GameModel, bob_game.id).score = 50
        db_session.commit()

        entries = games_service.get_daily_leaderboard(IMMICHDLE_TYPE, MODE_PERSON, d)

        assert [e.username for e in entries] == [alice.username, bob.username]
        assert [e.best_score for e in entries] == [90, 50]

    def test_unfinished_games_are_excluded(self, games_service, daily_settings_service, auth_service):
        daily_settings_service.update_settings(IMMICHDLE_TYPE, MODE_PERSON, enabled=True)
        d = _next_date()
        user = _register(auth_service)
        games_service.create_daily_game(game_type=IMMICHDLE_TYPE, mode=MODE_PERSON, user_id=user.id, today=d)

        assert games_service.get_daily_leaderboard(IMMICHDLE_TYPE, MODE_PERSON, d) == []

    def test_only_scopes_to_that_challenges_date(self, games_service, daily_settings_service, db_session, auth_service):
        daily_settings_service.update_settings(IMMICHDLE_TYPE, MODE_PERSON, enabled=True)
        day1 = _next_date()
        day2 = day1 + timedelta(days=1)
        user = _register(auth_service)
        game1 = games_service.create_daily_game(game_type=IMMICHDLE_TYPE, mode=MODE_PERSON, user_id=user.id, today=day1)
        db_session.get(GameModel, game1.id).finished = True
        db_session.get(GameModel, game1.id).score = 77
        db_session.commit()

        assert games_service.get_daily_leaderboard(IMMICHDLE_TYPE, MODE_PERSON, day2) == []
        day1_entries = games_service.get_daily_leaderboard(IMMICHDLE_TYPE, MODE_PERSON, day1)
        assert [e.best_score for e in day1_entries] == [77]
