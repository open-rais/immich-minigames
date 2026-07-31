"""Daily-challenge attempts (roadmap #G) - create_daily_game (the player's one attempt at today's
challenge) and get_daily_status (the `GET /daily` menu listing). Challenge *generation* itself is
services/daily_challenge_service.py's job; this module only turns an already-generated challenge
into a specific player's played GameModel row, via the same persistence/games_repository.py and
services/game_factory.py glue services/games_service.py uses for live games.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from games.base import BaseGame
from games.registry import GAMES
from persistence.games_repository import GameRepository
from services.daily_challenge_service import DailyChallengeService
from services.daily_settings import DailySettingsService
from services.errors import DailyAlreadyPlayedError, DailyNotEnabledError, UnsupportedGameError
from services.game_factory import GameFactory


@dataclass(frozen=True)
class DailyModeStatus:
    """One entry of the `GET /daily` menu listing (roadmap #G, docs/TODO/DAILY-GAMES.md §4.6) - the
    caller's status for one enabled daily mode, without generating a challenge just to list it (see
    DailyGamesService.get_daily_status)."""

    game_type: str
    mode: str
    status: Literal["not_played", "in_progress", "finished"]
    game_id: UUID | None
    score: int | None


class DailyGamesService:
    def __init__(
        self,
        repository: GameRepository,
        factory: GameFactory,
        daily_settings_service: DailySettingsService,
        daily_challenge_service: DailyChallengeService,
    ) -> None:
        self._repository = repository
        self._factory = factory
        self._daily_settings_service = daily_settings_service
        self._daily_challenge_service = daily_challenge_service

    def create_daily_game(self, game_type: str, mode: str, user_id: UUID, today: date | None = None) -> BaseGame:
        """Creates (and consumes) the caller's single daily attempt for today's challenge of this
        (game_type, mode). Never abandons a normal game of the same mode, nor a previous daily one
        - a challenge only ever gets one game per player at all, enforced below + by the DB's
        partial unique indexes (see docs/TODO/DAILY-GAMES.md §4.5). `today` is only ever overridden
        by tests; real callers always mean the server's actual today."""
        if (game_type, mode) not in GAMES:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")
        if not self._daily_settings_service.is_enabled(game_type, mode):
            raise DailyNotEnabledError(f"{game_type}/{mode} is not enabled for the daily rotation")

        challenge = self._daily_challenge_service.get_or_create_challenge(today or date.today(), game_type, mode)

        if self._repository.has_played_challenge(challenge.id, user_id):
            raise DailyAlreadyPlayedError(f"already played today's {game_type}/{mode} challenge")

        game = self._factory.build_daily(game_type, mode, challenge, game_id=uuid4())

        try:
            self._repository.save_new(game, user_id=user_id, daily_challenge_id=challenge.id)
        except IntegrityError as exc:
            # Backstop against the race two simultaneous requests (e.g. two tabs) could hit - the
            # pre-check above already covers the common case, this covers the window between it and
            # the commit (see the partial unique indexes on persistence/games.py's GameModel).
            self._repository.rollback()
            raise DailyAlreadyPlayedError(f"already played today's {game_type}/{mode} challenge") from exc
        return game

    def get_daily_status(self, user_id: UUID, today: date | None = None) -> list[DailyModeStatus]:
        """Every enabled mode's status for the caller, without generating a challenge just to list
        it (a mode nobody's played yet today simply has no challenge row, and reads as
        "not_played")."""
        today = today or date.today()
        enabled_modes = self._daily_settings_service.list_enabled()
        if not enabled_modes:
            return []

        # Two queries total (today's challenges for every enabled mode, then the caller's games for
        # those challenges) rather than two per mode - same results, keyed back to each mode below.
        challenge_by_mode = self._repository.challenges_for_date(today, enabled_modes)
        game_by_challenge_id = (
            self._repository.games_for_challenges([c.id for c in challenge_by_mode.values()], user_id)
            if challenge_by_mode
            else {}
        )

        statuses = []
        for game_type, mode in enabled_modes:
            challenge = challenge_by_mode.get((game_type, mode))
            game_row = game_by_challenge_id.get(challenge.id) if challenge is not None else None
            if game_row is None:
                statuses.append(DailyModeStatus(game_type, mode, "not_played", None, None))
            elif game_row.finished:
                statuses.append(DailyModeStatus(game_type, mode, "finished", game_row.id, game_row.score))
            else:
                statuses.append(DailyModeStatus(game_type, mode, "in_progress", game_row.id, None))
        return statuses
