"""
Games service - creates/loads/plays games. Bridges the game-logic layer (games/*.py, no
persistence awareness) and this app's own DB (persistence/games.py).
"""

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from games.base import BaseGame, BaseRound
from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr import MODE_DAYS_TO_DATE, DateguessrGame, DateguessrRound
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS, GeoguessrGame, GeoguessrRound
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import MODE_PERSON_ASSETS, MoreOrLessGame, MoreOrLessRound
from persistence.games import GameModel, RoundModel
from services.immich_service import ImmichService

_GAME_CLASSES: dict[tuple[str, str], type[BaseGame]] = {
    (MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS): MoreOrLessGame,
    (GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS): GeoguessrGame,
    (DATEGUESSR_TYPE, MODE_DAYS_TO_DATE): DateguessrGame,
}
_ROUND_CLASSES: dict[tuple[str, str], type[BaseRound]] = {
    (MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS): MoreOrLessRound,
    (GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS): GeoguessrRound,
    (DATEGUESSR_TYPE, MODE_DAYS_TO_DATE): DateguessrRound,
}


class UnsupportedGameError(Exception):
    pass


class GameNotFoundError(Exception):
    pass


class GameOwnershipError(Exception):
    pass


class RoundNotPendingError(Exception):
    pass


class GamesService:
    def __init__(self, session: Session, immich_service: ImmichService) -> None:
        self._session = session
        self._immich_service = immich_service

    def create_game(self, owner: str, game_type: str, mode: str) -> BaseGame:
        game_class = _GAME_CLASSES.get((game_type, mode))
        if game_class is None:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")

        game = game_class.start(id=uuid4(), owner=owner, immich_service=self._immich_service)
        self._save_new_game(game)
        return game

    def get_game(self, game_id: UUID, owner: str) -> BaseGame:
        return self._load_game(game_id, owner)

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

        round_class = _ROUND_CLASSES[(game_row.game_type, game_row.mode)]
        rounds = [
            round_class.from_payload(
                id=row.id,
                game_id=row.game_id,
                round_index=row.round_index,
                payload=row.payload,
                score_delta=row.score_delta,
            )
            for row in game_row.rounds
        ]

        game_class = _GAME_CLASSES[(game_row.game_type, game_row.mode)]
        return game_class(
            id=game_row.id,
            owner=game_row.owner,
            rounds=rounds,
            immich_service=self._immich_service,
            score=game_row.score,
            finished=game_row.finished,
        )

    def _save_new_game(self, game: BaseGame) -> None:
        game_row = GameModel(
            id=game.id,
            owner=game.owner,
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
