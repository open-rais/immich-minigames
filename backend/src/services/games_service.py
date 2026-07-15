"""
Games service - creates/loads/plays games. Bridges the game-logic layer (games/*.py, no
persistence awareness) and this app's own DB (persistence/games.py).
"""

from dataclasses import dataclass
from typing import Any
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


class UnsupportedGameError(Exception):
    pass


class GameNotFoundError(Exception):
    pass


class GameOwnershipError(Exception):
    pass


class RoundNotPendingError(Exception):
    pass


class GamesService:
    def __init__(
        self, session: Session, immich_service: ImmichService, ml_service: MLService | None = None
    ) -> None:
        self._session = session
        self._immich_service = immich_service
        # Optional/self-constructing like immich_service is elsewhere (see api/api.py's
        # get_immich_service) - only ImmichdleGame actually uses it (see _game_kwargs), but
        # GamesService owning it means it (and its DB engine) is created once per service instance
        # rather than hidden inside ImmichdleGame's own constructor, and can be swapped for a fake
        # in tests.
        self._ml_service = ml_service or MLService()

    def _game_kwargs(self, game_class: type[BaseGame]) -> dict[str, Any]:
        """Constructor/`start()` kwargs every game needs, plus whichever extra ones a specific game
        class needs beyond that - today only ImmichdleGame's MLService (see games/immichdle.py).
        Centralizing the "which game needs what" knowledge here means a new game with its own extra
        dependency only ever needs one line added in this one method, not a change spread across
        every call site that builds a game."""
        kwargs: dict[str, Any] = {"immich_service": self._immich_service}
        if game_class is ImmichdleGame:
            kwargs["ml_service"] = self._ml_service
        return kwargs

    def create_game(
        self, owner: str, game_type: str, mode: str, user_id: UUID | None = None
    ) -> BaseGame:
        spec = _GAMES.get((game_type, mode))
        if spec is None:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")

        game = spec.game_class.start(id=uuid4(), owner=owner, **self._game_kwargs(spec.game_class))
        self._save_new_game(game, user_id=user_id)
        return game

    def get_game(self, game_id: UUID, owner: str) -> BaseGame:
        return self._load_game(game_id, owner)

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

    def play_round(self, game_id: UUID, owner: str, round_id: UUID, guess: Any) -> BaseGame:
        """Plays the given round and returns the game with its updated state (the answered round
        is still in game.rounds, and game.current_round is the new pending round, if any)."""
        game = self._load_game(game_id, owner)
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

    def _load_game(self, game_id: UUID, owner: str) -> BaseGame:
        game_row = self._session.get(GameModel, game_id)
        if game_row is None:
            raise GameNotFoundError(f"game {game_id} not found")
        if game_row.owner != owner:
            raise GameOwnershipError(f"game {game_id} does not belong to this owner")

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
            **self._game_kwargs(spec.game_class),
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
        game_row = self._session.get(GameModel, game.id)
        game_row.score = game.score
        game_row.finished = game.finished

        round_row = self._session.get(RoundModel, answered_round.id)
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
