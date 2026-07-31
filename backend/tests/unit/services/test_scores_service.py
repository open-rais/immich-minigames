import itertools
import uuid
from datetime import date, datetime, timedelta

import pytest
from conftest import mint_invite_code

from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle import MODE_PERSON
from persistence.daily import DailyConfigModel
from persistence.games import GameModel
from services.errors import UnsupportedGameError


def _register_user(auth_service):
    # games.user_id is a real FK to users.id (see persistence/games.py), so tests exercising it
    # need an actual UserModel row, not just a random uuid.
    unique = uuid.uuid4().hex[:8]
    return auth_service.register(
        email=f"user-{unique}@example.com",
        username=f"user-{unique}",
        full_name="Test User",
        password="correct-horse-battery-staple",
        invite_code=mint_invite_code(),
    )


class TestPersonalRecords:
    """Records are a pure persistence-layer query (ScoresService.get_personal_records) - games here
    are seeded directly at whatever score/finished state is needed rather than played out for
    real, since it's the MAX(score)-per-(user, mode) query being tested, not game logic."""

    def _seed_game(self, games_service, db_session, *, user_id, score, finished=True):
        game = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user_id)
        row = db_session.get(GameModel, game.id)
        row.score = score
        row.finished = finished
        db_session.commit()
        return game

    def test_returns_the_highest_score_for_the_user(self, games_service, scores_service, db_session, auth_service):
        user = _register_user(auth_service)
        self._seed_game(games_service, db_session, user_id=user.id, score=3)
        self._seed_game(games_service, db_session, user_id=user.id, score=7)
        self._seed_game(games_service, db_session, user_id=user.id, score=5)

        records = scores_service.get_personal_records(user.id)

        assert len(records) == 1
        assert records[0].game_type == "more-or-less"
        assert records[0].mode == "personAssets"
        assert records[0].best_score == 7

    def test_unfinished_games_are_excluded(self, games_service, scores_service, db_session, auth_service):
        user = _register_user(auth_service)
        self._seed_game(games_service, db_session, user_id=user.id, score=100, finished=False)

        records = scores_service.get_personal_records(user.id)

        assert records == []

    def test_no_games_returns_an_empty_list(self, scores_service, auth_service):
        user = _register_user(auth_service)
        records = scores_service.get_personal_records(user.id)

        assert records == []

    def test_does_not_leak_a_different_users_records(self, games_service, scores_service, db_session, auth_service):
        alice = _register_user(auth_service)
        bob = _register_user(auth_service)
        self._seed_game(games_service, db_session, user_id=alice.id, score=50)
        self._seed_game(games_service, db_session, user_id=bob.id, score=9)

        records = scores_service.get_personal_records(bob.id)

        assert len(records) == 1
        assert records[0].best_score == 9


class TestLeaderboard:
    """Same persistence-layer-query testing philosophy as TestPersonalRecords - games are seeded
    directly at whatever score/finished/created_at state a test needs, not played out for real.
    Every assertion here checks membership/absence of its own known users rather than an exact
    count or `== []`, filtering by username or a distinctive seeded score - this table is not
    written to exclusively by this file (an HTTP-level game test can
    create and finish a real, logged-in game against the same game_type/mode), so an exact-count
    assertion can't assume isolation. test_limit_is_15 additionally seeds scores far above
    any realistically-reachable real one so its top-15 boundary check stays deterministic."""

    def _seed_game(
        self,
        games_service,
        db_session,
        *,
        user_id,
        score,
        finished=True,
        game_type="more-or-less",
        mode="personAssets",
        created_at=None,
    ):
        game = games_service.create_game(game_type=game_type, mode=mode, user_id=user_id)
        row = db_session.get(GameModel, game.id)
        row.score = score
        row.finished = finished
        if created_at is not None:
            row.created_at = created_at
        db_session.commit()
        return game

    def test_ranks_by_best_score_descending(self, games_service, scores_service, db_session, auth_service):
        alice = _register_user(auth_service)
        bob = _register_user(auth_service)
        carol = _register_user(auth_service)
        self._seed_game(games_service, db_session, user_id=alice.id, score=50)
        self._seed_game(games_service, db_session, user_id=bob.id, score=90)
        self._seed_game(games_service, db_session, user_id=carol.id, score=70)

        entries = scores_service.get_leaderboard("more-or-less", "personAssets", "all")

        ours = [e for e in entries if e.username in {alice.username, bob.username, carol.username}]
        assert [e.username for e in ours] == [bob.username, carol.username, alice.username]
        assert [e.best_score for e in ours] == [90, 70, 50]

    def test_one_row_per_user_not_per_game(self, games_service, scores_service, db_session, auth_service):
        user = _register_user(auth_service)
        self._seed_game(games_service, db_session, user_id=user.id, score=30)
        self._seed_game(games_service, db_session, user_id=user.id, score=80)
        self._seed_game(games_service, db_session, user_id=user.id, score=55)

        entries = scores_service.get_leaderboard("more-or-less", "personAssets", "all")

        ours = [e for e in entries if e.username == user.username]
        assert len(ours) == 1
        assert ours[0].best_score == 80

    def test_unfinished_games_are_excluded(self, games_service, scores_service, db_session, auth_service):
        user = _register_user(auth_service)
        self._seed_game(
            games_service,
            db_session,
            user_id=user.id,
            score=100,
            finished=False,
            game_type="dateguessr",
            mode="daysToDate",
        )

        entries = scores_service.get_leaderboard("dateguessr", "daysToDate", "all")

        assert user.username not in {e.username for e in entries}

    def test_window_cutoffs_exclude_older_games(self, games_service, scores_service, db_session, auth_service):
        recent_user = _register_user(auth_service)
        old_user = _register_user(auth_service)
        self._seed_game(
            games_service, db_session, user_id=recent_user.id, score=10, game_type="immichdle", mode="person"
        )
        # A high score, well outside both the daily and weekly cutoffs - a good canary: if the
        # window filtering were broken, this would wrongly win daily/weekly instead of just "all".
        self._seed_game(
            games_service,
            db_session,
            user_id=old_user.id,
            score=999,
            game_type="immichdle",
            mode="person",
            created_at=datetime.now() - timedelta(days=10),
        )

        all_time = scores_service.get_leaderboard("immichdle", "person", "all")
        weekly = scores_service.get_leaderboard("immichdle", "person", "weekly")
        daily = scores_service.get_leaderboard("immichdle", "person", "daily")

        # Subset/absence checks, not exact set equality (see this class's own
        # docstring: real HTTP-created entries can legitimately share this table).
        assert {recent_user.username, old_user.username} <= {e.username for e in all_time}
        assert recent_user.username in {e.username for e in weekly}
        assert old_user.username not in {e.username for e in weekly}
        assert recent_user.username in {e.username for e in daily}
        assert old_user.username not in {e.username for e in daily}

    def test_limit_is_15(self, games_service, scores_service, db_session, auth_service):
        # Scores start comfortably above any realistically-reachable real score (an HTTP-level
        # geoguessr test can finish a real, logged-in game against this same
        # table) - guarantees our 16 seeded rows occupy the entire top of the ranking regardless of
        # how many lower-scored real entries also exist, so the "16th squeezed out" boundary this
        # test checks stays deterministic.
        base = 10_000_000
        users = []
        for score in range(16):
            user = _register_user(auth_service)
            users.append(user)
            self._seed_game(
                games_service,
                db_session,
                user_id=user.id,
                score=base + score,
                game_type="geoguessr",
                mode="distanceBetweenGuess",
            )

        entries = scores_service.get_leaderboard("geoguessr", "distanceBetweenGuess", "all")

        assert len(entries) == 15
        ours = [e for e in entries if e.username in {u.username for u in users}]
        assert len(ours) == 15  # nothing else can outscore `base` - every slot is ours
        # The lowest of the 16 seeded scores (0) must be the one squeezed out.
        assert [e.best_score - base for e in ours] == list(range(15, 0, -1))
        assert [e.rank for e in ours] == list(range(1, 16))

    def test_unsupported_game_type_raises(self, scores_service):
        with pytest.raises(UnsupportedGameError):
            scores_service.get_leaderboard("geoguessr", "not-a-real-mode", "all")

    def test_no_games_returns_an_empty_list(self, scores_service):
        entries = scores_service.get_leaderboard("whos-that-person", "namedFaces", "all")

        assert entries == []


class TestGetRecentGames:
    """The profile "Ver juegos" modal's last-5 list."""

    def _seed_game(self, games_service, db_session, *, user_id, finished=True, abandoned=False, created_at=None):
        game = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user_id)
        row = db_session.get(GameModel, game.id)
        row.finished = finished
        row.abandoned = abandoned
        if created_at is not None:
            row.created_at = created_at
        db_session.commit()
        return game

    def test_includes_finished_and_abandoned_games(self, games_service, scores_service, db_session, auth_service):
        user = _register_user(auth_service)
        finished = self._seed_game(games_service, db_session, user_id=user.id, finished=True, abandoned=False)
        abandoned = self._seed_game(games_service, db_session, user_id=user.id, finished=False, abandoned=True)

        recent = scores_service.get_recent_games(user.id)

        assert {g.id for g in recent} == {finished.id, abandoned.id}

    def test_excludes_a_still_active_game(self, games_service, scores_service, db_session, auth_service):
        user = _register_user(auth_service)
        self._seed_game(games_service, db_session, user_id=user.id, finished=False, abandoned=False)

        recent = scores_service.get_recent_games(user.id)

        assert recent == []

    def test_orders_newest_first_and_caps_at_the_limit(self, games_service, scores_service, db_session, auth_service):
        user = _register_user(auth_service)
        games = [
            self._seed_game(games_service, db_session, user_id=user.id, created_at=datetime.now() - timedelta(days=i))
            for i in range(7)
        ]

        recent = scores_service.get_recent_games(user.id, limit=5)

        assert len(recent) == 5
        assert [g.id for g in recent] == [g.id for g in games[:5]]

    def test_only_returns_this_users_games(self, games_service, scores_service, db_session, auth_service):
        alice = _register_user(auth_service)
        bob = _register_user(auth_service)
        self._seed_game(games_service, db_session, user_id=bob.id)

        assert scores_service.get_recent_games(alice.id) == []


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


class TestGetDailyLeaderboard:
    def test_unsupported_mode_raises(self, scores_service):
        with pytest.raises(UnsupportedGameError):
            scores_service.get_daily_leaderboard(IMMICHDLE_TYPE, "not-a-real-mode", _next_date())

    def test_a_date_with_no_challenge_returns_empty(self, scores_service):
        assert scores_service.get_daily_leaderboard(IMMICHDLE_TYPE, MODE_PERSON, _next_date()) == []

    def test_scores_finished_games_of_that_challenge(
        self, daily_games_service, scores_service, daily_settings_service, db_session, auth_service
    ):
        daily_settings_service.update_settings(IMMICHDLE_TYPE, MODE_PERSON, enabled=True)
        d = _next_date()
        alice = _register_user(auth_service)
        bob = _register_user(auth_service)

        alice_game = daily_games_service.create_daily_game(
            game_type=IMMICHDLE_TYPE, mode=MODE_PERSON, user_id=alice.id, today=d
        )
        bob_game = daily_games_service.create_daily_game(
            game_type=IMMICHDLE_TYPE, mode=MODE_PERSON, user_id=bob.id, today=d
        )
        db_session.get(GameModel, alice_game.id).finished = True
        db_session.get(GameModel, alice_game.id).score = 90
        db_session.get(GameModel, bob_game.id).finished = True
        db_session.get(GameModel, bob_game.id).score = 50
        db_session.commit()

        entries = scores_service.get_daily_leaderboard(IMMICHDLE_TYPE, MODE_PERSON, d)

        assert [e.username for e in entries] == [alice.username, bob.username]
        assert [e.best_score for e in entries] == [90, 50]

    def test_unfinished_games_are_excluded(
        self, daily_games_service, scores_service, daily_settings_service, auth_service
    ):
        daily_settings_service.update_settings(IMMICHDLE_TYPE, MODE_PERSON, enabled=True)
        d = _next_date()
        user = _register_user(auth_service)
        daily_games_service.create_daily_game(game_type=IMMICHDLE_TYPE, mode=MODE_PERSON, user_id=user.id, today=d)

        assert scores_service.get_daily_leaderboard(IMMICHDLE_TYPE, MODE_PERSON, d) == []

    def test_only_scopes_to_that_challenges_date(
        self, daily_games_service, scores_service, daily_settings_service, db_session, auth_service
    ):
        daily_settings_service.update_settings(IMMICHDLE_TYPE, MODE_PERSON, enabled=True)
        day1 = _next_date()
        day2 = day1 + timedelta(days=1)
        user = _register_user(auth_service)
        game1 = daily_games_service.create_daily_game(
            game_type=IMMICHDLE_TYPE, mode=MODE_PERSON, user_id=user.id, today=day1
        )
        db_session.get(GameModel, game1.id).finished = True
        db_session.get(GameModel, game1.id).score = 77
        db_session.commit()

        assert scores_service.get_daily_leaderboard(IMMICHDLE_TYPE, MODE_PERSON, day2) == []
        day1_entries = scores_service.get_daily_leaderboard(IMMICHDLE_TYPE, MODE_PERSON, day1)
        assert [e.best_score for e in day1_entries] == [77]
