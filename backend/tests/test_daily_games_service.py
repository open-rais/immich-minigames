"""Roadmap #G, phase F0 - "daily games live in a separate world" (docs/TODO/DAILY-GAMES.md §4.5).

create_daily_game doesn't exist yet (that's F3) - these tests seed a daily game the same way the
rest of the suite seeds any other row state (create a normal game, then mutate its row directly),
attaching it to a directly-inserted DailyChallengeModel row.
"""

import itertools
import uuid
from datetime import date, timedelta

import pytest

from persistence.daily import DailyChallengeModel
from persistence.games import GameModel
from services.games_service import UnsupportedGameError

# (challenge_date, game_type, mode) is uniquely constrained (DailyChallengeModel) - these
# integration tests share one real DB across the whole session (no per-test transaction rollback,
# see conftest.py), so two tests that both default to "today" would collide. A distinct, ever-
# decreasing fake date per call keeps every seeded challenge unique without each test having to
# invent its own game_type/mode just to dodge the constraint.
_date_counter = itertools.count()


def _seed_challenge(db_session, *, game_type="more-or-less", mode="personAssets", challenge_date=None):
    challenge = DailyChallengeModel(
        id=uuid.uuid4(),
        challenge_date=challenge_date or date(2000, 1, 1) + timedelta(days=next(_date_counter)),
        game_type=game_type,
        mode=mode,
        spec={},
        settings={},
    )
    db_session.add(challenge)
    db_session.commit()
    return challenge


def _make_daily_game(games_service, db_session, *, owner, user_id=None, game_type="more-or-less", mode="personAssets"):
    challenge = _seed_challenge(db_session, game_type=game_type, mode=mode)
    game = games_service.create_game(owner=owner, game_type=game_type, mode=mode, user_id=user_id)
    row = db_session.get(GameModel, game.id)
    row.daily_challenge_id = challenge.id
    db_session.commit()
    return game, challenge


class TestDailyGamesExcludedFromPersonalRecords:
    def test_a_finished_daily_game_does_not_produce_a_record(self, games_service, db_session):
        owner = f"owner-{uuid.uuid4().hex[:8]}"
        game, _ = _make_daily_game(games_service, db_session, owner=owner)
        row = db_session.get(GameModel, game.id)
        row.finished = True
        row.score = 999
        db_session.commit()

        assert games_service.get_personal_records(owner, user_id=None) == []


class TestDailyGamesExcludedFromLeaderboard:
    def test_a_finished_daily_game_does_not_appear(self, games_service, db_session, auth_service):
        user = auth_service.register(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            username=f"user-{uuid.uuid4().hex[:8]}",
            full_name="Test User",
            password="correct-horse-battery-staple",
        )
        game, _ = _make_daily_game(
            games_service, db_session, owner="owner-a", user_id=user.id, game_type="dateguessr", mode="daysToDate"
        )
        row = db_session.get(GameModel, game.id)
        row.finished = True
        row.score = 999
        db_session.commit()

        entries = games_service.get_leaderboard("dateguessr", "daysToDate", "all")

        assert user.username not in {e.username for e in entries}


class TestDailyGamesExcludedFromCurrentGame:
    def test_an_in_progress_daily_game_is_not_offered_as_continuar(self, games_service, db_session):
        owner = f"owner-{uuid.uuid4().hex[:8]}"
        _make_daily_game(games_service, db_session, owner=owner)

        assert games_service.get_current_game(owner, "more-or-less", "personAssets", user_id=None) is None


class TestDailyGamesDoNotInteractWithAbandon:
    def test_starting_a_normal_game_does_not_abandon_an_in_progress_daily(self, games_service, db_session):
        owner = f"owner-{uuid.uuid4().hex[:8]}"
        daily_game, _ = _make_daily_game(games_service, db_session, owner=owner)

        games_service.create_game(owner=owner, game_type="more-or-less", mode="personAssets")

        row = db_session.get(GameModel, daily_game.id)
        assert row.abandoned is False

    # The reverse direction - creating a daily game must never abandon an in-progress normal game -
    # needs create_daily_game itself (F3) to exercise for real; covered there.


class TestGetRecentGamesFlagsDaily:
    def test_is_daily_flag_reflects_daily_challenge_id(self, games_service, db_session, auth_service):
        user = auth_service.register(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            username=f"user-{uuid.uuid4().hex[:8]}",
            full_name="Test User",
            password="correct-horse-battery-staple",
        )
        daily_game, _ = _make_daily_game(games_service, db_session, owner="owner-a", user_id=user.id)
        db_session.get(GameModel, daily_game.id).finished = True
        normal_game = games_service.create_game(
            owner="owner-a", game_type="more-or-less", mode="albumAssets", user_id=user.id
        )
        db_session.get(GameModel, normal_game.id).finished = True
        db_session.commit()

        recent = games_service.get_recent_games(user.id)

        by_id = {g.id: g for g in recent}
        assert by_id[daily_game.id].is_daily is True
        assert by_id[normal_game.id].is_daily is False


class TestGamesDailyChallengeIdRoundTrips:
    def test_partial_unique_index_rejects_a_second_anonymous_attempt(self, games_service, db_session):
        owner = f"owner-{uuid.uuid4().hex[:8]}"
        challenge = _seed_challenge(db_session)
        first = games_service.create_game(owner=owner, game_type="more-or-less", mode="personAssets")
        db_session.get(GameModel, first.id).daily_challenge_id = challenge.id
        db_session.commit()

        second = games_service.create_game(owner=owner, game_type="more-or-less", mode="personAssets")
        row = db_session.get(GameModel, second.id)
        row.daily_challenge_id = challenge.id
        # Same (challenge, owner), user_id NULL both times - the partial unique index on
        # (daily_challenge_id, owner) WHERE user_id IS NULL must reject this at flush time.
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_unsupported_game_type_still_raises_for_get_leaderboard(self, games_service):
        with pytest.raises(UnsupportedGameError):
            games_service.get_leaderboard("more-or-less", "not-a-real-mode", "all")
