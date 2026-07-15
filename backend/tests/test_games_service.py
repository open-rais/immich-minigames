import uuid

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
