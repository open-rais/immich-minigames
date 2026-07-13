import uuid

import pytest

from services.games_service import (
    GameNotFoundError,
    GameOwnershipError,
    RoundNotPendingError,
    UnsupportedGameError,
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
