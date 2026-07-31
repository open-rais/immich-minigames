"""Games service - creates/loads/plays live games (create_game, get_game, get_current_game,
play_round/play_loaded_round). Daily-challenge attempts live in services/daily_games_service.py,
and score/history reporting in services/scores_service.py - all three sit on top of
persistence/games_repository.py's GameRepository (queries/mutations on GameModel/RoundModel) and
services/game_factory.py's GameFactory (registry -> kwargs -> BaseGame), so none of the three
re-implements the other's persistence glue.

The (game_type, mode) -> game/round-class registry lives in games/registry.py, not here. Every
exception this service raises (NotEnoughContentError, GameNotFoundError, and the rest) lives in
services/errors.py rather than being defined here, so api/error_handlers.py's exception->status
table can import them without importing this whole service.
"""

from typing import Any
from uuid import UUID, uuid4

from games.base import BaseGame
from games.registry import GAMES
from persistence.games_repository import GameRepository
from persistence.users import UserModel
from services.errors import GameNotFoundError, GameOwnershipError, RoundNotPendingError, UnsupportedGameError
from services.game_factory import GameFactory


class GamesService:
    def __init__(self, repository: GameRepository, factory: GameFactory) -> None:
        self._repository = repository
        self._factory = factory

    def create_game(self, game_type: str, mode: str, user_id: UUID) -> BaseGame:
        spec = GAMES.get((game_type, mode))
        if spec is None:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")

        game = self._factory.build(spec, game_type, mode, game_id=uuid4())
        # Enforces "at most one active game per (player, mode)" server-side, so the frontend's
        # "Nuevo juego" button needs no separate abandon step: it's the same createGame call
        # "Jugar" always made, and this stays one atomic commit with save_new below.
        self._repository.abandon_active(game_type, mode, user_id)
        self._repository.save_new(game, user_id=user_id)
        return game

    def get_game(self, game_id: UUID, user: UserModel) -> BaseGame:
        return self._load_game(game_id, user)

    def get_current_game(self, game_type: str, mode: str, user_id: UUID) -> BaseGame | None:
        """Idle-screen "Continuar" lookup."""
        if (game_type, mode) not in GAMES:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")
        game_row = self._repository.get_active(game_type, mode, user_id)
        return self._factory.from_row(game_row) if game_row is not None else None

    def play_round(self, game_id: UUID, user: UserModel, round_id: UUID, guess: Any) -> BaseGame:
        """Plays the given round and returns the game with its updated state (the answered round
        is still in game.rounds, and game.current_round is the new pending round, if any)."""
        game = self._load_game(game_id, user)
        return self.play_loaded_round(game, round_id, guess)

    def play_loaded_round(self, game: BaseGame, round_id: UUID, guess: Any) -> BaseGame:
        """Same as play_round but on an already-loaded game (e.g. one just returned by get_game),
        avoiding a second DB read and rebuilding every round via from_payload a second time."""
        if game.finished or game.current_round.id != round_id:
            raise RoundNotPendingError(f"round {round_id} is not the current pending round of game {game.id}")

        answered_round = game.current_round
        game.play_round(guess)
        self._repository.save_played_round(game, answered_round)
        return game

    def _load_game(self, game_id: UUID, user: UserModel) -> BaseGame:
        game_row = self._repository.get_for_update(game_id)
        if game_row is None:
            raise GameNotFoundError(f"game {game_id} not found")
        if user.id != game_row.user_id:
            raise GameOwnershipError(f"game {game_id} does not belong to this user")
        return self._factory.from_row(game_row)
