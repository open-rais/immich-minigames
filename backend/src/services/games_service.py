"""
Games service - creates/loads/plays games. Bridges the game-logic layer (games/*.py, no
persistence awareness) and this app's own DB (persistence/games.py).
"""

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from games.base import BaseGame, BaseRound
from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr import MODE_DAYS_TO_DATE, DateguessrGame, DateguessrRound
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS, GeoguessrGame, GeoguessrRound
from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle import MODE_PERSON, ImmichdleGame, ImmichdleRound
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import MODE_PERSON_ASSETS, MoreOrLessGame, MoreOrLessRound
from games.whos_that_person import GAME_TYPE as WHOS_THAT_PERSON_TYPE
from games.whos_that_person import MODE_NAMED_FACES, WhosThatPersonGame, WhosThatPersonRound
from persistence.games import GameModel, RoundModel
from persistence.users import UserModel
from services.game_settings import GameSettingsService
from services.immich_service import ImmichService
from services.ml_service import MLService


@dataclass(frozen=True)
class _GameSpec:
    """One registry entry per (game_type, mode) - single source of truth for which game/round
    classes a combination maps to, so adding a game only ever means adding one entry here (used to
    be two separate dicts that had to stay in lockstep)."""

    game_class: type[BaseGame]
    round_class: type[BaseRound]


_GAMES: dict[tuple[str, str], _GameSpec] = {
    (MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS): _GameSpec(MoreOrLessGame, MoreOrLessRound),
    (GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS): _GameSpec(GeoguessrGame, GeoguessrRound),
    (DATEGUESSR_TYPE, MODE_DAYS_TO_DATE): _GameSpec(DateguessrGame, DateguessrRound),
    (IMMICHDLE_TYPE, MODE_PERSON): _GameSpec(ImmichdleGame, ImmichdleRound),
    (WHOS_THAT_PERSON_TYPE, MODE_NAMED_FACES): _GameSpec(WhosThatPersonGame, WhosThatPersonRound),
}


@dataclass(frozen=True)
class GameRecord:
    """One personal-best entry (roadmap point E) - a mode the owner/user has at least one finished
    game for, with their highest score in it."""

    game_type: str
    mode: str
    best_score: int


@dataclass(frozen=True)
class LeaderboardEntry:
    """One leaderboard row (roadmap point F) - a distinct account's best score for a (game_type,
    mode) within a time window, 1-indexed by rank. Anonymous games never produce a row (see
    get_leaderboard's join) - there's no account to show a name/photo for."""

    rank: int
    username: str
    skin_person_id: UUID | None
    best_score: int


class UnsupportedGameError(Exception):
    pass


class GameNotFoundError(Exception):
    pass


class GameOwnershipError(Exception):
    pass


class RoundNotPendingError(Exception):
    pass


class NotEnoughContentError(Exception):
    """Raised when the Immich library doesn't have enough named people/faces/located assets to
    start a game - the friendly ValueError each game's start() already raises for that case (see
    games/more_or_less.py, games/immichdle.py, games/whos_that_person.py, games/asset_rounds.py),
    re-raised here so main.py can map it to a 422 instead of it reaching the client as a bare 500."""


class GamesService:
    def __init__(
        self,
        session: Session,
        immich_service: ImmichService,
        ml_service: MLService | None = None,
        game_settings_service: GameSettingsService | None = None,
    ) -> None:
        self._session = session
        # Populated by _load_game() and consulted by _save_played_round() so playing a round never
        # has to re-fetch (and assume the existence of) a GameModel row this same service instance
        # already loaded earlier in the request (see docs/TODO/CODE-REVIEW.md #28).
        self._loaded_game_rows: dict[UUID, GameModel] = {}
        self._immich_service = immich_service
        # Optional/self-constructing like immich_service is elsewhere (see api/api.py's
        # get_immich_service) - only ImmichdleGame actually uses it (see _game_kwargs), but
        # GamesService owning it means it (and its DB engine) is created once per service instance
        # rather than hidden inside ImmichdleGame's own constructor, and can be swapped for a fake
        # in tests.
        self._ml_service = ml_service or MLService()
        # Admin feature (ADMIN-FEATURE.md point #4) - same optional/self-constructing pattern.
        self._game_settings_service = game_settings_service or GameSettingsService(session)

    def _game_kwargs(self, game_class: type[BaseGame], game_type: str) -> dict[str, Any]:
        """Constructor/`start()` kwargs every game needs, plus whichever extra ones a specific game
        class needs beyond that - today only ImmichdleGame's MLService (see games/immichdle.py).
        Centralizing the "which game needs what" knowledge here means a new game with its own extra
        dependency only ever needs one line added in this one method, not a change spread across
        every call site that builds a game. `game_type` is a plain str (not derived from
        `game_class`) since not every concrete game class exposes it as a class attribute - callers
        already have the string in scope (the (game_type, mode) key that picked this spec)."""
        kwargs: dict[str, Any] = {
            "immich_service": self._immich_service,
            "settings": self._game_settings_service.get_settings(game_type),
        }
        if game_class is ImmichdleGame:
            kwargs["ml_service"] = self._ml_service
        return kwargs

    def create_game(
        self, owner: str, game_type: str, mode: str, user_id: UUID | None = None
    ) -> BaseGame:
        spec = _GAMES.get((game_type, mode))
        if spec is None:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")

        try:
            game = spec.game_class.start(id=uuid4(), owner=owner, **self._game_kwargs(spec.game_class, game_type))
        except ValueError as e:
            raise NotEnoughContentError(str(e)) from e
        self._save_new_game(game, user_id=user_id)
        return game

    def get_game(self, game_id: UUID, owner: str, user: UserModel | None = None) -> BaseGame:
        return self._load_game(game_id, owner, user)

    def get_personal_records(self, owner: str, user_id: UUID | None) -> list[GameRecord]:
        """Roadmap point E - personal-best score per (game_type, mode), shown in the main menu.
        Filters by the account's user_id when logged in, otherwise by the anonymous browser's
        owner id - every game's score is higher-is-better (see games/asset_rounds.py's
        exp_decay_score and each game's win/streak-based deltas), so MAX(score) among finished
        games is a valid "best" for every existing game/mode."""
        filter_clause = GameModel.user_id == user_id if user_id is not None else GameModel.owner == owner
        rows = self._session.execute(
            select(GameModel.game_type, GameModel.mode, func.max(GameModel.score))
            .where(GameModel.finished.is_(True), filter_clause)
            .group_by(GameModel.game_type, GameModel.mode)
        ).all()
        return [GameRecord(game_type=gt, mode=m, best_score=best) for gt, m, best in rows]

    def get_leaderboard(
        self, game_type: str, mode: str, window: Literal["all", "weekly", "daily"]
    ) -> list[LeaderboardEntry]:
        """Roadmap point F - top 15 distinct accounts by their best score for this (game_type,
        mode), optionally restricted to games created since this week's/today's midnight (server
        time - see date_trunc below, computed in Postgres rather than Python so the cutoff is
        never skewed by a client/server clock or timezone mismatch, and lines up with how
        GameModel.created_at itself was written via server_default=func.now()). The inner join to
        UserModel is what excludes anonymous games (user_id is null there, so they never match)."""
        if (game_type, mode) not in _GAMES:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")

        best_score = func.max(GameModel.score).label("best_score")
        stmt = (
            select(UserModel.username, UserModel.skin_person_id, best_score)
            .join(UserModel, UserModel.id == GameModel.user_id)
            .where(GameModel.game_type == game_type, GameModel.mode == mode, GameModel.finished.is_(True))
            .group_by(UserModel.id, UserModel.username, UserModel.skin_person_id)
            .order_by(best_score.desc())
            .limit(15)
        )
        if window != "all":
            # Postgres's date_trunc('week', ...) is Monday-based (ISO 8601), matching "semanal
            # desde el lunes" as confirmed with the project owner.
            trunc_unit = "day" if window == "daily" else "week"
            stmt = stmt.where(GameModel.created_at >= func.date_trunc(trunc_unit, func.now()))

        rows = self._session.execute(stmt).all()
        return [
            LeaderboardEntry(rank=rank, username=username, skin_person_id=skin_person_id, best_score=score)
            for rank, (username, skin_person_id, score) in enumerate(rows, start=1)
        ]

    def play_round(
        self, game_id: UUID, owner: str, round_id: UUID, guess: Any, user: UserModel | None = None
    ) -> BaseGame:
        """Plays the given round and returns the game with its updated state (the answered round
        is still in game.rounds, and game.current_round is the new pending round, if any)."""
        game = self._load_game(game_id, owner, user)
        return self.play_loaded_round(game, round_id, guess)

    def play_loaded_round(self, game: BaseGame, round_id: UUID, guess: Any) -> BaseGame:
        """Same as play_round but on an already-loaded game (e.g. one just returned by get_game),
        avoiding a second DB read and rebuilding every round via from_payload a second time."""
        if game.finished or game.current_round.id != round_id:
            raise RoundNotPendingError(f"round {round_id} is not the current pending round of game {game.id}")

        answered_round = game.current_round
        game.play_round(guess)
        self._save_played_round(game, answered_round)
        return game

    # -- persistence glue ---------------------------------------------------

    def _load_game(self, game_id: UUID, owner: str, user: UserModel | None = None) -> BaseGame:
        # SELECT ... FOR UPDATE - this is the single load point for both viewing a game (get_game)
        # and loading it right before playing a round, so locking it here closes the race where two
        # simultaneous plays of the same round both pass play_loaded_round's current_round.id check
        # and both score (docs/TODO/CODE-REVIEW.md #6). Everything happens in one transaction per
        # request (api/deps.py's get_db_session), so the lock is held for at most one request.
        game_row = self._session.get(GameModel, game_id, with_for_update=True)
        if game_row is None:
            raise GameNotFoundError(f"game {game_id} not found")
        # A game created while logged in (user_id set) is owned by that account forever - the
        # X-Owner-Id header alone is no longer proof of ownership for it, even if it happens to
        # match (leaked via logs/Referer, or a shared browser/localStorage - see #3 in
        # docs/TODO/CODE-REVIEW.md). A game created anonymously (user_id NULL) stays owner-only,
        # even for a request that's since logged in - user_id is fixed at creation and never
        # backfilled, so "logged in" alone doesn't grant access to someone's past anonymous games.
        if game_row.user_id is not None:
            if user is None or user.id != game_row.user_id:
                raise GameOwnershipError(f"game {game_id} does not belong to this owner")
        elif game_row.owner != owner:
            raise GameOwnershipError(f"game {game_id} does not belong to this owner")

        self._loaded_game_rows[game_row.id] = game_row

        spec = _GAMES[(game_row.game_type, game_row.mode)]
        rounds = [
            spec.round_class.from_payload(
                id=row.id,
                game_id=row.game_id,
                round_index=row.round_index,
                payload=row.payload,
                score_delta=row.score_delta,
            )
            for row in game_row.rounds
        ]

        return spec.game_class(
            id=game_row.id,
            owner=game_row.owner,
            rounds=rounds,
            score=game_row.score,
            finished=game_row.finished,
            **self._game_kwargs(spec.game_class, game_row.game_type),
        )

    def _save_new_game(self, game: BaseGame, user_id: UUID | None = None) -> None:
        game_row = GameModel(
            id=game.id,
            owner=game.owner,
            user_id=user_id,
            game_type=game.game_type,
            mode=game.mode,
            score=game.score,
            finished=game.finished,
        )
        game_row.rounds.append(self._round_to_row(game.rounds[0]))
        self._session.add(game_row)
        self._session.commit()

    def _save_played_round(self, game: BaseGame, answered_round: BaseRound) -> None:
        # No session.get() re-fetch here - the row was already loaded (and, on the play path,
        # FOR UPDATE-locked) by _load_game earlier in this same service instance/request, so
        # re-querying it by id would be redundant and, being Optional, would need an unjustified
        # existence check for a row we know is already in the session (see CODE-REVIEW.md #28).
        game_row = self._loaded_game_rows.get(game.id)
        if game_row is None:
            raise RuntimeError(f"_save_played_round called for game {game.id}, which was never loaded via _load_game")
        game_row.score = game.score
        game_row.finished = game.finished

        round_row = next((r for r in game_row.rounds if r.id == answered_round.id), None)
        if round_row is None:
            raise RuntimeError(f"round {answered_round.id} not found among already-loaded rows of game {game.id}")
        round_row.score_delta = answered_round.score_delta
        round_row.payload = answered_round.to_payload()

        if game.rounds[-1].id != answered_round.id:
            game_row.rounds.append(self._round_to_row(game.rounds[-1]))

        self._session.commit()

    @staticmethod
    def _round_to_row(round_: BaseRound) -> RoundModel:
        return RoundModel(
            id=round_.id,
            round_index=round_.round_index,
            score_delta=round_.score_delta,
            payload=round_.to_payload(),
        )
