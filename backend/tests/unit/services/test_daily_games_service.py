"""Tests for DailyGamesService.create_daily_game / get_daily_status / the daily branch
of GameFactory.from_row. Integration tests against the real dev Immich DB (see conftest.py's module
docstring)."""

import itertools
import uuid
from datetime import date, timedelta

import pytest
from conftest import mint_invite_code

from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS
from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle import MODE_PERSON
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import MODE_PERSON_ASSETS
from persistence.daily import DailyConfigModel
from persistence.games import GameModel
from services.errors import DailyAlreadyPlayedError, DailyNotEnabledError, UnsupportedGameError

_date_counter = itertools.count()
_BASE_DATE = date(2030, 1, 1)

_TOUCHED_GAME_TYPES = [MORE_OR_LESS_TYPE, GEOGUESSR_TYPE, IMMICHDLE_TYPE]


def _next_date() -> date:
    return _BASE_DATE + timedelta(days=next(_date_counter) * 1000)


def _register_user(auth_service):
    unique = uuid.uuid4().hex[:8]
    return auth_service.register(
        email=f"user-{unique}@example.com",
        username=f"user-{unique}",
        full_name="Test User",
        password="correct-horse-battery-staple",
        invite_code=mint_invite_code(),
    )


@pytest.fixture(autouse=True)
def _clean_daily_configs(db_session):
    def _clear():
        db_session.query(DailyConfigModel).filter(DailyConfigModel.game_type.in_(_TOUCHED_GAME_TYPES)).delete(
            synchronize_session=False
        )
        db_session.commit()

    _clear()
    yield
    _clear()


class TestCreateDailyGame:
    def test_not_enabled_raises(self, games_service, daily_games_service, auth_service):
        user = _register_user(auth_service)
        with pytest.raises(DailyNotEnabledError):
            daily_games_service.create_daily_game(
                game_type=GEOGUESSR_TYPE, mode=MODE_DISTANCE_BETWEEN_GUESS, user_id=user.id, today=_next_date()
            )

    def test_unsupported_mode_raises(self, games_service, daily_games_service, auth_service):
        user = _register_user(auth_service)
        with pytest.raises(UnsupportedGameError):
            daily_games_service.create_daily_game(
                game_type=GEOGUESSR_TYPE, mode="not-a-real-mode", user_id=user.id, today=_next_date()
            )

    def test_creates_a_game_with_the_challenge_content(
        self, games_service, daily_games_service, daily_settings_service, auth_service
    ):
        daily_settings_service.update_settings(
            GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, enabled=True, values={"total_rounds": 2}
        )
        user = _register_user(auth_service)
        d = _next_date()

        game = daily_games_service.create_daily_game(
            game_type=GEOGUESSR_TYPE, mode=MODE_DISTANCE_BETWEEN_GUESS, user_id=user.id, today=d
        )

        assert game.total_rounds == 2
        assert game.daily_challenge_date == d

    def test_second_attempt_by_the_same_player_raises(
        self, games_service, daily_games_service, daily_settings_service, auth_service
    ):
        daily_settings_service.update_settings(
            MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS, enabled=True, values={"chain_length": 10}
        )
        user = _register_user(auth_service)
        d = _next_date()
        daily_games_service.create_daily_game(
            game_type=MORE_OR_LESS_TYPE, mode=MODE_PERSON_ASSETS, user_id=user.id, today=d
        )

        with pytest.raises(DailyAlreadyPlayedError):
            daily_games_service.create_daily_game(
                game_type=MORE_OR_LESS_TYPE, mode=MODE_PERSON_ASSETS, user_id=user.id, today=d
            )

    def test_a_different_player_can_still_play_the_same_challenge(
        self, games_service, daily_games_service, daily_settings_service, auth_service
    ):
        daily_settings_service.update_settings(
            MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS, enabled=True, values={"chain_length": 10}
        )
        alice = _register_user(auth_service)
        bob = _register_user(auth_service)
        d = _next_date()
        daily_games_service.create_daily_game(
            game_type=MORE_OR_LESS_TYPE, mode=MODE_PERSON_ASSETS, user_id=alice.id, today=d
        )

        second = daily_games_service.create_daily_game(
            game_type=MORE_OR_LESS_TYPE, mode=MODE_PERSON_ASSETS, user_id=bob.id, today=d
        )

        assert second is not None

    def test_two_players_get_identical_scripted_content(
        self, games_service, daily_games_service, daily_settings_service, auth_service
    ):
        daily_settings_service.update_settings(
            GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, enabled=True, values={"total_rounds": 3}
        )
        alice = _register_user(auth_service)
        bob = _register_user(auth_service)
        d = _next_date()

        a = daily_games_service.create_daily_game(
            game_type=GEOGUESSR_TYPE, mode=MODE_DISTANCE_BETWEEN_GUESS, user_id=alice.id, today=d
        )
        b = daily_games_service.create_daily_game(
            game_type=GEOGUESSR_TYPE, mode=MODE_DISTANCE_BETWEEN_GUESS, user_id=bob.id, today=d
        )

        assert a.rounds[0].asset.latitude == b.rounds[0].asset.latitude
        assert a.rounds[0].asset.longitude == b.rounds[0].asset.longitude

    def test_does_not_abandon_an_in_progress_normal_game(
        self, games_service, daily_games_service, daily_settings_service, db_session, auth_service
    ):
        daily_settings_service.update_settings(
            MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS, enabled=True, values={"chain_length": 10}
        )
        user = _register_user(auth_service)
        normal_game = games_service.create_game(game_type=MORE_OR_LESS_TYPE, mode=MODE_PERSON_ASSETS, user_id=user.id)

        daily_games_service.create_daily_game(
            game_type=MORE_OR_LESS_TYPE, mode=MODE_PERSON_ASSETS, user_id=user.id, today=_next_date()
        )

        row = db_session.get(GameModel, normal_game.id)
        assert row.abandoned is False


class TestMoreOrLessDailyChainExhaustion:
    def test_playing_through_the_whole_chain_ends_as_perfect(
        self, games_service, daily_games_service, daily_settings_service, auth_service
    ):
        daily_settings_service.update_settings(
            MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS, enabled=True, values={"chain_length": 10}
        )
        user = _register_user(auth_service)
        d = _next_date()
        game = daily_games_service.create_daily_game(
            game_type=MORE_OR_LESS_TYPE, mode=MODE_PERSON_ASSETS, user_id=user.id, today=d
        )
        game_id = game.id

        while not game.finished:
            round_ = game.current_round
            # Regression guard: a bug in the scripted provider's resume index once made round 2
            # replay the same chain entry as both reference and candidate (reported as "el segundo
            # y tercer personajes están repetidos") - a self-tie that the score assertion below
            # alone wouldn't catch, since a tie still scores 1 like a real win.
            assert round_.reference.id != round_.candidate.id
            guess = "more" if round_.candidate.value > round_.reference.value else "less"
            game = games_service.play_round(game_id, user, round_.id, guess)

        # A 10-length chain (chain_length + 1 = 11 entities) means 10 winnable rounds - reached the
        # end without ever guessing wrong, so the final score is exactly the chain length.
        assert game.score == 10


class TestResumeDailyGame:
    def test_resuming_continues_the_chain_at_the_right_index(
        self, games_service, daily_games_service, daily_settings_service, auth_service
    ):
        daily_settings_service.update_settings(
            MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS, enabled=True, values={"chain_length": 10}
        )
        user = _register_user(auth_service)
        d = _next_date()
        game = daily_games_service.create_daily_game(
            game_type=MORE_OR_LESS_TYPE, mode=MODE_PERSON_ASSETS, user_id=user.id, today=d
        )
        first_round = game.current_round
        guess = "more" if first_round.candidate.value > first_round.reference.value else "less"
        played = games_service.play_round(game.id, user, first_round.id, guess)
        assert played.finished is False

        reloaded = games_service.get_game(game.id, user)

        assert reloaded.current_round.id == played.current_round.id
        assert reloaded.daily_challenge_date == d

    def test_resuming_past_the_boundary_still_plays_against_the_original_challenge(
        self, games_service, daily_games_service, daily_settings_service, auth_service
    ):
        # Resuming after midnight: loading an in-progress daily
        # game must always reconstruct it from *its own* challenge, never "today's", regardless of
        # what today actually is when it's reloaded.
        daily_settings_service.update_settings(
            GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, enabled=True, values={"total_rounds": 3}
        )
        user = _register_user(auth_service)
        d = _next_date()
        game = daily_games_service.create_daily_game(
            game_type=GEOGUESSR_TYPE, mode=MODE_DISTANCE_BETWEEN_GUESS, user_id=user.id, today=d
        )

        reloaded = games_service.get_game(game.id, user)

        assert reloaded.daily_challenge_date == d
        assert reloaded.rounds[0].asset.latitude == game.rounds[0].asset.latitude


class TestGetDailyStatus:
    def test_not_played_when_no_game_exists(
        self, games_service, daily_games_service, daily_settings_service, auth_service
    ):
        daily_settings_service.update_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, enabled=True)
        user = _register_user(auth_service)
        d = _next_date()

        statuses = daily_games_service.get_daily_status(user.id, d)

        geo = next(s for s in statuses if s.game_type == GEOGUESSR_TYPE)
        assert geo.status == "not_played"
        assert geo.game_id is None

    def test_in_progress_then_finished(self, games_service, daily_games_service, daily_settings_service, auth_service):
        daily_settings_service.update_settings(IMMICHDLE_TYPE, MODE_PERSON, enabled=True)
        user = _register_user(auth_service)
        d = _next_date()
        game = daily_games_service.create_daily_game(
            game_type=IMMICHDLE_TYPE, mode=MODE_PERSON, user_id=user.id, today=d
        )

        statuses = daily_games_service.get_daily_status(user.id, d)
        in_progress = next(s for s in statuses if s.game_type == IMMICHDLE_TYPE)
        assert in_progress.status == "in_progress"
        assert in_progress.game_id == game.id

        played = games_service.play_round(game.id, user, game.current_round.id, game.target.id)
        assert played.finished is True

        statuses_after = daily_games_service.get_daily_status(user.id, d)
        finished = next(s for s in statuses_after if s.game_type == IMMICHDLE_TYPE)
        assert finished.status == "finished"
        assert finished.score == played.score

    def test_disabled_mode_is_not_listed(self, games_service, daily_games_service, auth_service):
        user = _register_user(auth_service)
        d = _next_date()

        statuses = daily_games_service.get_daily_status(user.id, d)

        assert not any(s.game_type == GEOGUESSR_TYPE for s in statuses)
