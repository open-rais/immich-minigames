"""Registry -> kwargs -> BaseGame - the "pegamento de persistencia" every service that builds or
rebuilds a game needs (services/games_service.py for live games, services/daily_games_service.py
for daily ones), extracted so neither has to duplicate the "which extra kwarg does this concrete
game class need" knowledge, and so a new game only ever needs a line added here.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from games.base import BaseGame
from games.immichdle import ImmichdleGame
from games.registry import GAMES, GameSpec
from games.whos_that_person import WhosThatPersonGame
from persistence.daily import DailyChallengeModel
from persistence.games import GameModel
from services.errors import NotEnoughContentError, UnsupportedGameError
from services.game_settings_service import GameSettingsService
from services.immich import ImmichService
from services.ml_service import MLService


class GameFactory:
    def __init__(
        self,
        session: Session,
        immich_service: ImmichService,
        ml_service: MLService,
        game_settings_service: GameSettingsService,
    ) -> None:
        self._session = session
        self._immich_service = immich_service
        self._ml_service = ml_service
        self._game_settings_service = game_settings_service

    def kwargs_for(self, spec: GameSpec, game_type: str, mode: str) -> dict[str, Any]:
        """Constructor/`start()` kwargs every game needs, plus whichever extra ones a specific game
        class needs beyond that. Centralizing the "which game needs what" knowledge here means a
        new game with its own extra dependency only ever needs one line added in this one method,
        not a change spread across every call site that builds a game. `game_type`/`mode` are plain
        strs (not derived from `game_class`) since not every concrete game class exposes them -
        callers already have the (game_type, mode) key that picked this spec in scope."""
        kwargs: dict[str, Any] = {
            "settings": self._game_settings_service.get_settings(game_type, mode),
        }
        if spec.provider_factory is not None:
            # The provider fully replaces this game's data source, so it gets provider + mode
            # instead of immich_service/content (see games/registry.py's GameSpec).
            kwargs["provider"] = spec.provider_factory(self._immich_service)
            kwargs["mode"] = mode
        elif spec.content_factory is not None:
            # The content object fully replaces this game's data source too (Geoguessr/Dateguessr)
            # - except WhosThatPerson, which still needs immich_service directly below for live
            # guess-name resolution, unrelated to content.
            kwargs["content"] = spec.content_factory(self._immich_service)
        else:
            kwargs["immich_service"] = self._immich_service
        if spec.game_class is ImmichdleGame:
            kwargs["ml_service"] = self._ml_service
        if spec.game_class is WhosThatPersonGame:
            kwargs["immich_service"] = self._immich_service
        return kwargs

    def daily_kwargs_for(
        self, game_type: str, mode: str, challenge: DailyChallengeModel, *, rounds_played: int
    ) -> dict[str, Any]:
        """Kwargs for a daily game - mirrors kwargs_for's role but sources content from the frozen
        challenge spec/settings snapshot instead of live Immich queries or admin-configured live
        settings. Delegates the actual per-game decisions to that (game_type, mode)'s own
        `games/<game>/daily.py::game_kwargs()` (this registry lookup is the single dispatch point,
        not a second dict to keep in sync). `rounds_played` is how many rounds already exist (0
        right before calling .start(), or len(persisted rounds) when reconstructing an
        in-progress game via from_row) - only a game whose scripted source needs to resume
        mid-sequence actually uses it."""
        spec = GAMES.get((game_type, mode))
        if spec is None or spec.daily is None:
            raise UnsupportedGameError(f"unsupported daily game/mode: {game_type}/{mode}")
        return spec.daily.game_kwargs(
            mode,
            challenge.spec,
            challenge.settings,
            rounds_played=rounds_played,
            immich_service=self._immich_service,
            ml_service=self._ml_service,
        )

    def build(self, spec: GameSpec, game_type: str, mode: str, game_id: UUID) -> BaseGame:
        try:
            return spec.game_class.start(id=game_id, **self.kwargs_for(spec, game_type, mode))
        except ValueError as e:
            raise NotEnoughContentError(str(e)) from e

    def build_daily(self, game_type: str, mode: str, challenge: DailyChallengeModel, game_id: UUID) -> BaseGame:
        # Daily games use the *same* class a normal game does - only the content source differs,
        # via daily_kwargs_for above.
        kwargs = self.daily_kwargs_for(game_type, mode, challenge, rounds_played=0)
        try:
            game = GAMES[(game_type, mode)].game_class.start(id=game_id, **kwargs)
        except ValueError as e:
            raise NotEnoughContentError(str(e)) from e
        game.daily_challenge_date = challenge.challenge_date
        return game

    def from_row(self, game_row: GameModel) -> BaseGame:
        """Reconstructs a BaseGame from an already-fetched GameModel row - shared by every caller
        that loads a game back from the DB (a locked load right before playing a round, the idle
        screen's "Continuar" lookup, ...)."""
        spec = GAMES[(game_row.game_type, game_row.mode)]
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

        if game_row.daily_challenge_id is not None:
            # A daily game's class/kwargs come from its frozen challenge, not the live
            # settings/Immich queries every normal game uses (see daily_kwargs_for).
            challenge = self._session.get(DailyChallengeModel, game_row.daily_challenge_id)
            if challenge is None:
                raise RuntimeError(f"game {game_row.id} references a missing daily challenge")
            game = spec.game_class(
                id=game_row.id,
                rounds=rounds,
                score=game_row.score,
                finished=game_row.finished,
                **self.daily_kwargs_for(game_row.game_type, game_row.mode, challenge, rounds_played=len(rounds)),
            )
            game.daily_challenge_date = challenge.challenge_date
            return game

        return spec.game_class(
            id=game_row.id,
            rounds=rounds,
            score=game_row.score,
            finished=game_row.finished,
            **self.kwargs_for(spec, game_row.game_type, game_row.mode),
        )
