import threading
import uuid

import pytest
from conftest import mint_invite_code

from persistence.base import get_session_factory
from persistence.games import GameModel
from persistence.games_repository import GameRepository
from services.errors import (
    GameNotFoundError,
    GameOwnershipError,
    NotEnoughContentError,
    RoundNotPendingError,
    UnsupportedGameError,
)
from services.game_factory import GameFactory
from services.game_settings_service import GameSettingsService
from services.games_service import GamesService


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


def _correct_guess(round_) -> str:
    return "more" if round_.candidate.value > round_.reference.value else "less"


def _wrong_guess(round_) -> str:
    return "less" if round_.candidate.value > round_.reference.value else "more"


class TestCreateGame:
    def test_persists_the_game_and_its_first_round(self, games_service, auth_service):
        user = _register_user(auth_service)
        game = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)

        reloaded = games_service.get_game(game.id, user)

        assert reloaded.score == 0
        assert reloaded.finished is False
        assert len(reloaded.rounds) == 1
        assert reloaded.rounds[0].reference.name == game.rounds[0].reference.name

    def test_unsupported_game_type_raises(self, games_service, auth_service):
        user = _register_user(auth_service)
        with pytest.raises(UnsupportedGameError):
            games_service.create_game(game_type="geoguessr", mode="default", user_id=user.id)

    def test_not_enough_content_raises_not_enough_content_error(
        self, games_service, immich_service, monkeypatch, auth_service
    ):
        # A game's start() raises a plain ValueError for "library too small" (see
        # games/more_or_less.py, games/immichdle.py) - create_game must translate it into
        # NotEnoughContentError so main.py can map it to a 422 instead of a bare 500.
        monkeypatch.setattr(immich_service, "get_persons", lambda **kwargs: [])
        user = _register_user(auth_service)

        with pytest.raises(NotEnoughContentError, match="not enough entities"):
            games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)

    def test_user_id_is_persisted(self, games_service, db_session, auth_service):
        user = _register_user(auth_service)
        game = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)

        row = db_session.get(GameModel, game.id)
        assert row.user_id == user.id


class TestCreateGameAbandonsPreviousActiveGame:
    """Creating a new game marks any other still-active game of the same
    (user, game_type, mode) as abandoned, so the idle screen's "Continuar" lookup
    (get_current_game) only ever finds the most recently started one."""

    def test_abandons_the_previous_unfinished_game_of_the_same_mode(self, games_service, db_session, auth_service):
        user = _register_user(auth_service)
        first = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)

        games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)

        row = db_session.get(GameModel, first.id)
        assert row.abandoned is True
        assert row.finished is False  # abandoned is orthogonal to finished, not a substitute for it

    def test_does_not_touch_a_different_mode(self, games_service, db_session, auth_service):
        user = _register_user(auth_service)
        first = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)

        games_service.create_game(game_type="more-or-less", mode="albumAssets", user_id=user.id)

        row = db_session.get(GameModel, first.id)
        assert row.abandoned is False

    def test_does_not_touch_an_already_finished_game(self, games_service, db_session, auth_service):
        user = _register_user(auth_service)
        first = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)
        row = db_session.get(GameModel, first.id)
        row.finished = True
        db_session.commit()

        games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)

        db_session.refresh(row)
        assert row.abandoned is False

    def test_a_legacy_stray_unfinished_game_also_gets_abandoned(self, games_service, db_session, auth_service):
        # Simulates a game created before the `abandoned` column existed - self-heals rather than
        # assuming there's ever only one active row to find.
        user = _register_user(auth_service)
        first = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)
        second = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)
        # Undo the abandon the second create_game just did, to simulate two stray active rows.
        db_session.get(GameModel, first.id).abandoned = False
        db_session.commit()

        games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)

        assert db_session.get(GameModel, first.id).abandoned is True
        assert db_session.get(GameModel, second.id).abandoned is True


class TestGetGame:
    def test_wrong_user_raises(self, games_service, auth_service):
        alice = _register_user(auth_service)
        bob = _register_user(auth_service)
        game = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=alice.id)

        with pytest.raises(GameOwnershipError):
            games_service.get_game(game.id, bob)

    def test_missing_game_raises(self, games_service, auth_service):
        user = _register_user(auth_service)
        with pytest.raises(GameNotFoundError):
            games_service.get_game(uuid.uuid4(), user)


class TestPlayRound:
    def test_correct_guess_persists_the_new_round(self, games_service, auth_service):
        user = _register_user(auth_service)
        game = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)
        first_round = game.rounds[0]

        played = games_service.play_round(game.id, user, first_round.id, _correct_guess(first_round))

        assert played.score == 1
        assert played.finished is False
        assert len(played.rounds) == 2

        reloaded = games_service.get_game(game.id, user)
        assert reloaded.score == 1
        assert len(reloaded.rounds) == 2
        assert reloaded.rounds[0].guess == _correct_guess(first_round)

    def test_wrong_guess_finishes_the_game(self, games_service, auth_service):
        user = _register_user(auth_service)
        game = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)
        first_round = game.rounds[0]

        played = games_service.play_round(game.id, user, first_round.id, _wrong_guess(first_round))

        assert played.finished is True
        reloaded = games_service.get_game(game.id, user)
        assert reloaded.finished is True

    def test_playing_a_non_pending_round_raises(self, games_service, auth_service):
        user = _register_user(auth_service)
        game = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)
        first_round = game.rounds[0]
        games_service.play_round(game.id, user, first_round.id, _wrong_guess(first_round))

        with pytest.raises(RoundNotPendingError):
            games_service.play_round(game.id, user, first_round.id, "more")


class TestPlayRoundConcurrency:
    def test_simultaneous_plays_of_the_same_round_do_not_double_score(
        self, games_service, immich_service, ml_service, auth_service
    ):
        # Two independent sessions, exactly like two real concurrent HTTP requests would get
        # (api/deps.py's get_db_session hands out a fresh Session per request): without the FOR
        # UPDATE lock in _load_game, both could pass play_loaded_round's current_round.id check
        # and both score.
        user = _register_user(auth_service)
        game = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)
        first_round = game.rounds[0]
        guess = _correct_guess(first_round)

        session_b = get_session_factory()()
        try:
            repository_b = GameRepository(session_b)
            factory_b = GameFactory(session_b, immich_service, ml_service, GameSettingsService(session_b))
            service_b = GamesService(repository_b, factory_b)

            # Load (and lock) the row via the service under test, but don't commit yet - simulates
            # request A having read the game and being about to play it.
            loaded_a = games_service._load_game(game.id, user)

            b_result = {}

            def run_b():
                try:
                    b_result["game"] = service_b.play_round(game.id, user, first_round.id, guess)
                except Exception as exc:  # RoundNotPendingError, expected once unblocked
                    b_result["error"] = exc

            t = threading.Thread(target=run_b)
            t.start()
            t.join(timeout=0.3)
            assert not b_result  # still blocked on A's FOR UPDATE lock

            # A finishes playing and commits, releasing the lock.
            games_service.play_loaded_round(loaded_a, first_round.id, guess)

            t.join(timeout=2)
        finally:
            session_b.close()

        # B must have seen A's committed result once unblocked, not double-scored.
        assert isinstance(b_result.get("error"), RoundNotPendingError)
        reloaded = games_service.get_game(game.id, user)
        assert reloaded.score == 1


class TestGetCurrentGame:
    """The idle screen's "Continuar" lookup."""

    def test_no_active_game_returns_none(self, games_service, auth_service):
        user = _register_user(auth_service)

        assert games_service.get_current_game("more-or-less", "personAssets", user.id) is None

    def test_returns_the_active_game(self, games_service, auth_service):
        user = _register_user(auth_service)
        game = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)

        current = games_service.get_current_game("more-or-less", "personAssets", user.id)

        assert current is not None
        assert current.id == game.id

    def test_ignores_a_finished_game(self, games_service, db_session, auth_service):
        user = _register_user(auth_service)
        game = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)
        row = db_session.get(GameModel, game.id)
        row.finished = True
        db_session.commit()

        assert games_service.get_current_game("more-or-less", "personAssets", user.id) is None

    def test_ignores_an_abandoned_game(self, games_service, db_session, auth_service):
        user = _register_user(auth_service)
        game = games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=user.id)
        row = db_session.get(GameModel, game.id)
        row.abandoned = True
        db_session.commit()

        assert games_service.get_current_game("more-or-less", "personAssets", user.id) is None

    def test_scopes_by_user_id(self, games_service, auth_service):
        alice = _register_user(auth_service)
        bob = _register_user(auth_service)
        games_service.create_game(game_type="more-or-less", mode="personAssets", user_id=alice.id)

        assert games_service.get_current_game("more-or-less", "personAssets", bob.id) is None

    def test_unsupported_game_type_raises(self, games_service, auth_service):
        user = _register_user(auth_service)
        with pytest.raises(UnsupportedGameError):
            games_service.get_current_game("geoguessr", "not-a-real-mode", user.id)
