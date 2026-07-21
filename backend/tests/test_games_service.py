import uuid
from datetime import datetime, timedelta

import pytest

from persistence.games import GameModel
from services.games_service import (
    GameNotFoundError,
    GameOwnershipError,
    RoundNotPendingError,
    UnsupportedGameError,
)


def _register_user(auth_service):
    # games.user_id is a real FK to users.id (see persistence/games.py), so tests exercising it
    # need an actual UserModel row, not just a random uuid.
    unique = uuid.uuid4().hex[:8]
    return auth_service.register(
        email=f"user-{unique}@example.com",
        username=f"user-{unique}",
        full_name="Test User",
        password="correct-horse-battery-staple",
    )


def _correct_guess(round_) -> str:
    return "more" if round_.candidate.asset_count > round_.reference.asset_count else "less"


def _wrong_guess(round_) -> str:
    return "less" if round_.candidate.asset_count > round_.reference.asset_count else "more"


class TestCreateGame:
    def test_persists_the_game_and_its_first_round(self, games_service):
        game = games_service.create_game(owner="owner-a", game_type="more-or-less", mode="personAssets")

        reloaded = games_service.get_game(game.id, owner="owner-a")

        assert reloaded.score == 0
        assert reloaded.finished is False
        assert len(reloaded.rounds) == 1
        assert reloaded.rounds[0].reference.name == game.rounds[0].reference.name

    def test_unsupported_game_type_raises(self, games_service):
        with pytest.raises(UnsupportedGameError):
            games_service.create_game(owner="owner-a", game_type="geoguessr", mode="default")

    def test_user_id_is_persisted_when_given(self, games_service, db_session, auth_service):
        user = _register_user(auth_service)
        game = games_service.create_game(
            owner="owner-a", game_type="more-or-less", mode="personAssets", user_id=user.id
        )

        row = db_session.get(GameModel, game.id)
        assert row.user_id == user.id

    def test_user_id_defaults_to_none_for_anonymous_play(self, games_service, db_session):
        game = games_service.create_game(owner="owner-a", game_type="more-or-less", mode="personAssets")

        row = db_session.get(GameModel, game.id)
        assert row.user_id is None


class TestGetGame:
    def test_wrong_owner_raises(self, games_service):
        game = games_service.create_game(owner="owner-a", game_type="more-or-less", mode="personAssets")

        with pytest.raises(GameOwnershipError):
            games_service.get_game(game.id, owner="someone-else")

    def test_missing_game_raises(self, games_service):
        with pytest.raises(GameNotFoundError):
            games_service.get_game(uuid.uuid4(), owner="owner-a")

    def test_logged_in_game_is_reachable_by_user_even_with_wrong_owner_header(self, games_service, auth_service):
        # The account is the real proof of ownership once a game is tied to one - a stale/rotated
        # X-Owner-Id shouldn't lock the owner out of their own game (see docs/TODO/CODE-REVIEW.md #3).
        alice = _register_user(auth_service)
        game = games_service.create_game(
            owner="owner-a", game_type="more-or-less", mode="personAssets", user_id=alice.id
        )

        reloaded = games_service.get_game(game.id, owner="someone-else", user=alice)

        assert reloaded.id == game.id

    def test_logged_in_game_rejects_a_different_account_even_with_matching_owner_header(
        self, games_service, auth_service
    ):
        # This is the actual bug #3 fixes: a leaked/guessed X-Owner-Id used to be enough on its
        # own to read and play someone else's logged-in game.
        alice = _register_user(auth_service)
        bob = _register_user(auth_service)
        game = games_service.create_game(
            owner="owner-a", game_type="more-or-less", mode="personAssets", user_id=alice.id
        )

        with pytest.raises(GameOwnershipError):
            games_service.get_game(game.id, owner="owner-a", user=bob)

    def test_logged_in_game_rejects_an_anonymous_request_even_with_matching_owner_header(
        self, games_service, auth_service
    ):
        alice = _register_user(auth_service)
        game = games_service.create_game(
            owner="owner-a", game_type="more-or-less", mode="personAssets", user_id=alice.id
        )

        with pytest.raises(GameOwnershipError):
            games_service.get_game(game.id, owner="owner-a", user=None)

    def test_anonymous_game_stays_owner_only_even_for_a_logged_in_request(self, games_service, auth_service):
        # user_id is fixed at creation and never backfilled - logging in later doesn't grant
        # access to a game started anonymously under a different/wrong owner id.
        alice = _register_user(auth_service)
        game = games_service.create_game(owner="owner-a", game_type="more-or-less", mode="personAssets")

        with pytest.raises(GameOwnershipError):
            games_service.get_game(game.id, owner="someone-else", user=alice)

    def test_anonymous_game_is_still_reachable_by_owner_while_logged_in(self, games_service, auth_service):
        alice = _register_user(auth_service)
        game = games_service.create_game(owner="owner-a", game_type="more-or-less", mode="personAssets")

        reloaded = games_service.get_game(game.id, owner="owner-a", user=alice)

        assert reloaded.id == game.id


class TestPlayRound:
    def test_correct_guess_persists_the_new_round(self, games_service):
        game = games_service.create_game(owner="owner-a", game_type="more-or-less", mode="personAssets")
        first_round = game.rounds[0]

        played = games_service.play_round(game.id, "owner-a", first_round.id, _correct_guess(first_round))

        assert played.score == 1
        assert played.finished is False
        assert len(played.rounds) == 2

        reloaded = games_service.get_game(game.id, owner="owner-a")
        assert reloaded.score == 1
        assert len(reloaded.rounds) == 2
        assert reloaded.rounds[0].guess == _correct_guess(first_round)

    def test_wrong_guess_finishes_the_game(self, games_service):
        game = games_service.create_game(owner="owner-a", game_type="more-or-less", mode="personAssets")
        first_round = game.rounds[0]

        played = games_service.play_round(game.id, "owner-a", first_round.id, _wrong_guess(first_round))

        assert played.finished is True
        reloaded = games_service.get_game(game.id, owner="owner-a")
        assert reloaded.finished is True

    def test_playing_a_non_pending_round_raises(self, games_service):
        game = games_service.create_game(owner="owner-a", game_type="more-or-less", mode="personAssets")
        first_round = game.rounds[0]
        games_service.play_round(game.id, "owner-a", first_round.id, _wrong_guess(first_round))

        with pytest.raises(RoundNotPendingError):
            games_service.play_round(game.id, "owner-a", first_round.id, "more")


class TestPersonalRecords:
    """Records are a pure persistence-layer query (GamesService.get_personal_records) - games here
    are seeded directly at whatever score/finished state is needed rather than played out for
    real, since it's the MAX(score)-per-(owner-or-user, mode) query being tested, not game logic."""

    def _seed_game(self, games_service, db_session, *, owner, user_id=None, score, finished=True):
        game = games_service.create_game(
            owner=owner, game_type="more-or-less", mode="personAssets", user_id=user_id
        )
        row = db_session.get(GameModel, game.id)
        row.score = score
        row.finished = finished
        db_session.commit()
        return game

    def test_returns_the_highest_score_for_the_owner(self, games_service, db_session):
        owner = f"owner-{uuid.uuid4().hex[:8]}"
        self._seed_game(games_service, db_session, owner=owner, score=3)
        self._seed_game(games_service, db_session, owner=owner, score=7)
        self._seed_game(games_service, db_session, owner=owner, score=5)

        records = games_service.get_personal_records(owner, user_id=None)

        assert len(records) == 1
        assert records[0].game_type == "more-or-less"
        assert records[0].mode == "personAssets"
        assert records[0].best_score == 7

    def test_unfinished_games_are_excluded(self, games_service, db_session):
        owner = f"owner-{uuid.uuid4().hex[:8]}"
        self._seed_game(games_service, db_session, owner=owner, score=100, finished=False)

        records = games_service.get_personal_records(owner, user_id=None)

        assert records == []

    def test_no_games_returns_an_empty_list(self, games_service):
        records = games_service.get_personal_records(f"owner-{uuid.uuid4().hex[:8]}", user_id=None)

        assert records == []

    def test_logged_in_filters_by_user_id_not_owner(self, games_service, db_session, auth_service):
        # Same browser owner id used for both an anonymous game and a logged-in one - the
        # logged-in query must key off user_id, not fall through to owner, or a shared browser
        # could leak an unrelated account's record.
        owner = f"owner-{uuid.uuid4().hex[:8]}"
        user = _register_user(auth_service)
        self._seed_game(games_service, db_session, owner=owner, user_id=None, score=50)
        self._seed_game(games_service, db_session, owner=owner, user_id=user.id, score=9)

        records = games_service.get_personal_records(owner, user_id=user.id)

        assert len(records) == 1
        assert records[0].best_score == 9


class TestLeaderboard:
    """Same persistence-layer-query testing philosophy as TestPersonalRecords - games are seeded
    directly at whatever score/finished/created_at state a test needs, not played out for real.
    Tests that need an exact row count use a game_type/mode no other test in this file seeds a
    finished+user_id game for (see the per-test game_type/mode below), so unrelated tests' data
    can't pollute an exact-count assertion; tests that only check relative order/membership among
    their own named users reuse the default "more-or-less"/"personAssets" and filter by username."""

    def _seed_game(
        self,
        games_service,
        db_session,
        *,
        user_id=None,
        score,
        finished=True,
        game_type="more-or-less",
        mode="personAssets",
        created_at=None,
    ):
        game = games_service.create_game(
            owner=f"owner-{uuid.uuid4().hex[:8]}", game_type=game_type, mode=mode, user_id=user_id
        )
        row = db_session.get(GameModel, game.id)
        row.score = score
        row.finished = finished
        if created_at is not None:
            row.created_at = created_at
        db_session.commit()
        return game

    def test_ranks_by_best_score_descending(self, games_service, db_session, auth_service):
        alice = _register_user(auth_service)
        bob = _register_user(auth_service)
        carol = _register_user(auth_service)
        self._seed_game(games_service, db_session, user_id=alice.id, score=50)
        self._seed_game(games_service, db_session, user_id=bob.id, score=90)
        self._seed_game(games_service, db_session, user_id=carol.id, score=70)

        entries = games_service.get_leaderboard("more-or-less", "personAssets", "all")

        ours = [e for e in entries if e.username in {alice.username, bob.username, carol.username}]
        assert [e.username for e in ours] == [bob.username, carol.username, alice.username]
        assert [e.best_score for e in ours] == [90, 70, 50]

    def test_one_row_per_user_not_per_game(self, games_service, db_session, auth_service):
        user = _register_user(auth_service)
        self._seed_game(games_service, db_session, user_id=user.id, score=30)
        self._seed_game(games_service, db_session, user_id=user.id, score=80)
        self._seed_game(games_service, db_session, user_id=user.id, score=55)

        entries = games_service.get_leaderboard("more-or-less", "personAssets", "all")

        ours = [e for e in entries if e.username == user.username]
        assert len(ours) == 1
        assert ours[0].best_score == 80

    def test_anonymous_games_are_excluded(self, games_service, db_session):
        self._seed_game(
            games_service, db_session, user_id=None, score=9999, game_type="dateguessr", mode="daysToDate"
        )

        entries = games_service.get_leaderboard("dateguessr", "daysToDate", "all")

        assert entries == []

    def test_unfinished_games_are_excluded(self, games_service, db_session, auth_service):
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

        entries = games_service.get_leaderboard("dateguessr", "daysToDate", "all")

        assert entries == []

    def test_window_cutoffs_exclude_older_games(self, games_service, db_session, auth_service):
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

        all_time = games_service.get_leaderboard("immichdle", "person", "all")
        weekly = games_service.get_leaderboard("immichdle", "person", "weekly")
        daily = games_service.get_leaderboard("immichdle", "person", "daily")

        assert {e.username for e in all_time} == {recent_user.username, old_user.username}
        assert {e.username for e in weekly} == {recent_user.username}
        assert {e.username for e in daily} == {recent_user.username}

    def test_limit_is_15(self, games_service, db_session, auth_service):
        for score in range(16):
            user = _register_user(auth_service)
            self._seed_game(
                games_service,
                db_session,
                user_id=user.id,
                score=score,
                game_type="geoguessr",
                mode="distanceBetweenGuess",
            )

        entries = games_service.get_leaderboard("geoguessr", "distanceBetweenGuess", "all")

        assert len(entries) == 15
        # The lowest of the 16 seeded scores (0) must be the one squeezed out.
        assert [e.best_score for e in entries] == list(range(15, 0, -1))
        assert [e.rank for e in entries] == list(range(1, 16))

    def test_unsupported_game_type_raises(self, games_service):
        with pytest.raises(UnsupportedGameError):
            games_service.get_leaderboard("geoguessr", "not-a-real-mode", "all")

    def test_no_games_returns_an_empty_list(self, games_service):
        entries = games_service.get_leaderboard("whos-that-person", "namedFaces", "all")

        assert entries == []
