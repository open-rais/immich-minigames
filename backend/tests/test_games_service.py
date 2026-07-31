import threading
import uuid
from datetime import datetime, timedelta

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
    """Roadmap #e - creating a new game marks any other still-active game of the same
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
        # (api/deps.py's get_db_session hands out a fresh Session per request) - this is what
        # docs/TODO/CODE-REVIEW.md #6 is about: without the FOR UPDATE lock in _load_game, both
        # could pass play_loaded_round's current_round.id check and both score.
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
    count or `== []`, filtering by username or a distinctive seeded score - roadmap #H, F3 means
    this table is no longer written to exclusively by this file (an HTTP-level game test can now
    create and finish a real, logged-in game against the same game_type/mode), so an exact-count
    assertion can't assume isolation anymore. test_limit_is_15 additionally seeds scores far above
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

        # Subset/absence checks, not exact set equality (roadmap #H, F3 - see this class's own
        # docstring: real HTTP-created entries can legitimately share this table now).
        assert {recent_user.username, old_user.username} <= {e.username for e in all_time}
        assert recent_user.username in {e.username for e in weekly}
        assert old_user.username not in {e.username for e in weekly}
        assert recent_user.username in {e.username for e in daily}
        assert old_user.username not in {e.username for e in daily}

    def test_limit_is_15(self, games_service, scores_service, db_session, auth_service):
        # Scores start comfortably above any realistically-reachable real score (roadmap #H, F3 -
        # an HTTP-level geoguessr test can now finish a real, logged-in game against this same
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


class TestGetCurrentGame:
    """Roadmap #e - the idle screen's "Continuar" lookup."""

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


class TestGetRecentGames:
    """Roadmap #e - the profile "Ver juegos" modal's last-5 list."""

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
