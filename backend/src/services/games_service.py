"""
Games service - creates/loads/plays games. Bridges the game-logic layer (games/*.py, no
persistence awareness) and this app's own DB (persistence/games.py).

NotEnoughContentError/UnsupportedGameError are defined in services/errors.py, not here, and
re-exported below - services/daily_service.py needs to raise the exact same NotEnoughContentError
this module's own games raise, and importing it back from here would cycle (this module also
imports DailyService). Every existing `from services.games_service import NotEnoughContentError`
call site (main.py, api/dto/common.py, tests/*) keeps working unchanged via that re-export.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from games.base import BaseGame, BaseRound
from games.daily_scripted import DailyDateguessrGame, DailyGeoguessrGame, DailyWhosThatPersonGame
from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr import MODE_DAYS_TO_DATE, DateguessrGame, DateguessrRound
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS, GeoguessrGame, GeoguessrRound
from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle import MODE_PERSON, ImmichdleGame, ImmichdleRound, PersonSnapshot
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import (
    MODE_ALBUM_ASSETS,
    MODE_PERSON_ASSETS,
    AlbumAssetsProvider,
    CandidateProvider,
    EntitySnapshot,
    MoreOrLessGame,
    MoreOrLessRound,
    PersonAssetsProvider,
    ScriptedCandidateProvider,
)
from games.whos_that_person import GAME_TYPE as WHOS_THAT_PERSON_TYPE
from games.whos_that_person import MODE_NAMED_FACES, WhosThatPersonGame, WhosThatPersonRound
from persistence.daily import DailyChallengeModel
from persistence.games import GameModel, RoundModel
from persistence.users import UserModel
from services.daily_service import DailyService
from services.daily_settings import DailySettingsService
from services.errors import NotEnoughContentError, UnsupportedGameError  # noqa: F401
from services.game_settings import GameSettingsService
from services.immich_service import ImmichService
from services.ml_service import MLService


@dataclass(frozen=True)
class _GameSpec:
    """One registry entry per (game_type, mode) - single source of truth for which game/round
    classes a combination maps to, so adding a game only ever means adding one entry here (used to
    be two separate dicts that had to stay in lockstep).

    `provider_factory` is only set for multi-mode games whose modes differ solely in their data
    source (MoreOrLess: personAssets vs albumAssets). When present, GamesService builds the provider
    and hands the game `provider` + `mode` *instead of* immich_service - the provider fully replaces
    the game's data source, so it has no other use for immich_service directly."""

    game_class: type[BaseGame]
    round_class: type[BaseRound]
    provider_factory: Callable[[ImmichService], CandidateProvider] | None = None


_GAMES: dict[tuple[str, str], _GameSpec] = {
    (MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS): _GameSpec(
        MoreOrLessGame, MoreOrLessRound, provider_factory=PersonAssetsProvider
    ),
    (MORE_OR_LESS_TYPE, MODE_ALBUM_ASSETS): _GameSpec(
        MoreOrLessGame, MoreOrLessRound, provider_factory=AlbumAssetsProvider
    ),
    (GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS): _GameSpec(GeoguessrGame, GeoguessrRound),
    (DATEGUESSR_TYPE, MODE_DAYS_TO_DATE): _GameSpec(DateguessrGame, DateguessrRound),
    (IMMICHDLE_TYPE, MODE_PERSON): _GameSpec(ImmichdleGame, ImmichdleRound),
    (WHOS_THAT_PERSON_TYPE, MODE_NAMED_FACES): _GameSpec(WhosThatPersonGame, WhosThatPersonRound),
}

# Roadmap #G - which game class a daily game of this game_type is built from instead of the normal
# one in _GAMES above (games/daily_scripted.py's thin subclasses, which replay a frozen spec
# instead of querying Immich). Keyed by game_type alone (not mode) since each of these three games
# has exactly one mode; MoreOrLess and Immichdle aren't here at all - they stay their normal game
# class, just constructed with a ScriptedCandidateProvider / a pre-picked target instead (see
# GamesService._daily_game_kwargs).
_DAILY_GAME_CLASSES: dict[str, type[BaseGame]] = {
    GEOGUESSR_TYPE: DailyGeoguessrGame,
    DATEGUESSR_TYPE: DailyDateguessrGame,
    WHOS_THAT_PERSON_TYPE: DailyWhosThatPersonGame,
}


@dataclass(frozen=True)
class GameRecord:
    """One personal-best entry (roadmap point E) - a mode the owner/user has at least one finished
    game for, with their highest score in it."""

    game_type: str
    mode: str
    best_score: int


@dataclass(frozen=True)
class RecentGame:
    """One row of the profile's "Ver juegos" modal (roadmap point #e) - a logged-in account's last
    N games that reached a final state, either by finishing naturally or by being abandoned when
    the player started a new one of that (game_type, mode). A still-active game never appears here
    - see GamesService.get_recent_games."""

    id: UUID
    game_type: str
    mode: str
    score: int
    finished: bool
    abandoned: bool
    created_at: datetime
    # Roadmap #G - whether this was a daily-challenge game rather than a normal one. Unlike every
    # other per-player query in this file, get_recent_games doesn't filter daily games out (it's
    # personal history, not a score comparison) - it just flags them so the "Ver juegos" modal can
    # label them (see docs/TODO/DAILY-GAMES.md §4.5).
    is_daily: bool


@dataclass(frozen=True)
class LeaderboardEntry:
    """One leaderboard row (roadmap point F) - a distinct account's best score for a (game_type,
    mode) within a time window, 1-indexed by rank. Anonymous games never produce a row (see
    get_leaderboard's join) - there's no account to show a name/photo for."""

    rank: int
    username: str
    skin_person_id: UUID | None
    best_score: int


@dataclass(frozen=True)
class DailyModeStatus:
    """One entry of the `GET /daily` menu listing (roadmap #G, docs/TODO/DAILY-GAMES.md §4.6) - the
    caller's (owner-or-user) status for one enabled daily mode, without generating a challenge just
    to list it (see GamesService.get_daily_status)."""

    game_type: str
    mode: str
    status: Literal["not_played", "in_progress", "finished"]
    game_id: UUID | None
    score: int | None


class GameNotFoundError(Exception):
    pass


class GameOwnershipError(Exception):
    pass


class RoundNotPendingError(Exception):
    pass


class DailyNotEnabledError(Exception):
    """Roadmap #G - raised by create_daily_game when the (game_type, mode) isn't in today's daily
    rotation (either genuinely unsupported, or a real mode the admin hasn't enabled) - main.py maps
    this to a 404, matching docs/TODO/DAILY-GAMES.md §4.6."""


class DailyAlreadyPlayedError(Exception):
    """Roadmap #G - raised by create_daily_game when the caller (owner-or-user) already has a game
    for today's challenge of this (game_type, mode) - "1 intento por día" (decision [C]). main.py
    maps this to a 409."""


class GamesService:
    def __init__(
        self,
        session: Session,
        immich_service: ImmichService,
        ml_service: MLService | None = None,
        game_settings_service: GameSettingsService | None = None,
        daily_settings_service: DailySettingsService | None = None,
        daily_service: DailyService | None = None,
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
        # Roadmap #G - same optional/self-constructing pattern as above.
        self._daily_settings_service = daily_settings_service or DailySettingsService(session)
        self._daily_service = daily_service or DailyService(session, immich_service)

    def _game_kwargs(self, spec: _GameSpec, game_type: str, mode: str) -> dict[str, Any]:
        """Constructor/`start()` kwargs every game needs, plus whichever extra ones a specific game
        class needs beyond that - ImmichdleGame's MLService (see games/immichdle.py), and, for a
        provider-based multi-mode game (MoreOrLess), its per-mode `provider` + `mode`. Centralizing
        the "which game needs what" knowledge here means a new game with its own extra dependency
        only ever needs one line added in this one method, not a change spread across every call
        site that builds a game. `game_type`/`mode` are plain strs (not derived from `game_class`)
        since not every concrete game class exposes them - callers already have the (game_type, mode)
        key that picked this spec in scope."""
        kwargs: dict[str, Any] = {
            "settings": self._game_settings_service.get_settings(game_type, mode),
        }
        if spec.provider_factory is not None:
            # The provider fully replaces this game's data source, so it gets provider + mode
            # instead of immich_service (see _GameSpec.provider_factory).
            kwargs["provider"] = spec.provider_factory(self._immich_service)
            kwargs["mode"] = mode
        else:
            kwargs["immich_service"] = self._immich_service
        if spec.game_class is ImmichdleGame:
            kwargs["ml_service"] = self._ml_service
        return kwargs

    def _daily_game_kwargs(
        self, game_type: str, mode: str, challenge: DailyChallengeModel, *, rounds_played: int
    ) -> dict[str, Any]:
        """Kwargs for a daily game's class - mirrors _game_kwargs's role but sources content from
        the frozen challenge spec/settings snapshot (docs/TODO/DAILY-GAMES.md §4.2, §4.4) instead
        of live Immich queries or admin-configured live settings. `rounds_played` is how many
        rounds already exist (0 right before calling .start(), or len(persisted rounds) when
        reconstructing an in-progress game in _row_to_game) - only MoreOrLess's scripted provider
        needs it, to resume mid-chain at the right index; Immichdle only needs the target on the
        very first round (rounds_played == 0), since ImmichdleRound.from_payload already carries it
        for every later reconstruction."""
        settings = challenge.settings
        if game_type == MORE_OR_LESS_TYPE:
            chain = [EntitySnapshot.from_dict(e) for e in challenge.spec["chain"]]
            # start() consumes chain[0] (reference) + chain[1] (first candidate); each further
            # round played consumes one more - see games/more_or_less.py's ScriptedCandidateProvider.
            next_index = rounds_played + 1
            return {"provider": ScriptedCandidateProvider(chain, next_index), "mode": mode, "settings": settings}
        if game_type in (GEOGUESSR_TYPE, DATEGUESSR_TYPE, WHOS_THAT_PERSON_TYPE):
            return {
                "immich_service": self._immich_service,  # unused for content, still a required param
                "settings": settings,
                "rounds_spec": challenge.spec["rounds"],
            }
        if game_type == IMMICHDLE_TYPE:
            kwargs: dict[str, Any] = {
                "immich_service": self._immich_service,
                "ml_service": self._ml_service,
                "settings": settings,
            }
            if rounds_played == 0:
                kwargs["target"] = PersonSnapshot.from_dict(challenge.spec["target"])
            return kwargs
        raise UnsupportedGameError(f"unsupported daily game/mode: {game_type}/{mode}")

    def create_game(
        self, owner: str, game_type: str, mode: str, user_id: UUID | None = None
    ) -> BaseGame:
        spec = _GAMES.get((game_type, mode))
        if spec is None:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")

        try:
            game = spec.game_class.start(id=uuid4(), owner=owner, **self._game_kwargs(spec, game_type, mode))
        except ValueError as e:
            raise NotEnoughContentError(str(e)) from e
        # Roadmap #e - enforces "at most one active game per (player, mode)" server-side, so the
        # frontend's "Nuevo juego" button needs no separate abandon step: it's the same createGame
        # call "Jugar" always made, and this stays one atomic commit with _save_new_game below.
        self._abandon_active_games(owner, game_type, mode, user_id)
        self._save_new_game(game, user_id=user_id)
        return game

    def create_daily_game(
        self, owner: str, game_type: str, mode: str, user_id: UUID | None = None, today: date | None = None
    ) -> BaseGame:
        """Roadmap #G, F3 - creates (and consumes) the caller's single daily attempt for today's
        challenge of this (game_type, mode). Never calls _abandon_active_games - a daily game
        neither abandons a normal game of the same mode nor a previous daily one (a challenge only
        ever gets one game per player at all, enforced below + by the DB's partial unique indexes -
        see docs/TODO/DAILY-GAMES.md §4.5). `today` is only ever overridden by tests; real callers
        always mean the server's actual today (decision [G])."""
        if (game_type, mode) not in _GAMES:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")
        if not self._daily_settings_service.is_enabled(game_type, mode):
            raise DailyNotEnabledError(f"{game_type}/{mode} is not enabled for the daily rotation")

        challenge = self._daily_service.get_or_create_challenge(today or date.today(), game_type, mode)

        filter_clause = GameModel.user_id == user_id if user_id is not None else GameModel.owner == owner
        already_played = self._session.execute(
            select(GameModel.id).where(GameModel.daily_challenge_id == challenge.id, filter_clause)
        ).scalar_one_or_none()
        if already_played is not None:
            raise DailyAlreadyPlayedError(f"already played today's {game_type}/{mode} challenge")

        game_class = _DAILY_GAME_CLASSES.get(game_type, _GAMES[(game_type, mode)].game_class)
        kwargs = self._daily_game_kwargs(game_type, mode, challenge, rounds_played=0)
        try:
            game = game_class.start(id=uuid4(), owner=owner, **kwargs)
        except ValueError as e:
            raise NotEnoughContentError(str(e)) from e
        game.daily_challenge_date = challenge.challenge_date

        try:
            self._save_new_game(game, user_id=user_id, daily_challenge_id=challenge.id)
        except IntegrityError as exc:
            # Backstop against the race two simultaneous requests (e.g. two tabs) could hit - the
            # pre-check above already covers the common case, this covers the window between it and
            # the commit (see the partial unique indexes on persistence/games.py's GameModel).
            self._session.rollback()
            raise DailyAlreadyPlayedError(f"already played today's {game_type}/{mode} challenge") from exc
        return game

    def get_daily_status(self, owner: str, user_id: UUID | None, today: date | None = None) -> list[DailyModeStatus]:
        """`GET /daily` menu listing (roadmap #G, §4.6) - every enabled mode's status for the
        caller, without generating a challenge just to list it (a mode nobody's played yet today
        simply has no challenge row, and reads as "not_played")."""
        today = today or date.today()
        enabled_modes = self._daily_settings_service.list_enabled()
        if not enabled_modes:
            return []
        filter_clause = GameModel.user_id == user_id if user_id is not None else GameModel.owner == owner

        # Two queries total (today's challenges for every enabled mode, then the caller's games for
        # those challenges) rather than two per mode - same results, keyed back to each mode below.
        challenge_by_mode = {
            (challenge.game_type, challenge.mode): challenge
            for challenge in self._session.execute(
                select(DailyChallengeModel).where(
                    DailyChallengeModel.challenge_date == today,
                    tuple_(DailyChallengeModel.game_type, DailyChallengeModel.mode).in_(enabled_modes),
                )
            ).scalars()
        }
        game_by_challenge_id: dict[UUID, GameModel] = {}
        if challenge_by_mode:
            game_by_challenge_id = {
                row.daily_challenge_id: row
                for row in self._session.execute(
                    select(GameModel).where(
                        GameModel.daily_challenge_id.in_([c.id for c in challenge_by_mode.values()]),
                        filter_clause,
                    )
                ).scalars()
            }

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

    def get_game(self, game_id: UUID, owner: str, user: UserModel | None = None) -> BaseGame:
        return self._load_game(game_id, owner, user)

    def get_current_game(
        self, owner: str, game_type: str, mode: str, user_id: UUID | None
    ) -> BaseGame | None:
        """Idle-screen "Continuar" lookup (roadmap #e) - works anonymously too (the route uses
        get_current_user_optional), matching "ya sea loggeado o no". Same owner-vs-user_id
        branching as get_personal_records. `ORDER BY created_at DESC LIMIT 1` rather than
        scalar_one() deliberately tolerates more than one matching row (a stray unfinished game
        left over from before the `abandoned` column existed, or the documented cross-tab race in
        _abandon_active_games) by just picking the most recent, instead of crashing."""
        if (game_type, mode) not in _GAMES:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")
        filter_clause = GameModel.user_id == user_id if user_id is not None else GameModel.owner == owner
        game_row = self._session.execute(
            select(GameModel)
            .where(
                GameModel.game_type == game_type,
                GameModel.mode == mode,
                GameModel.finished.is_(False),
                GameModel.abandoned.is_(False),
                # Roadmap #G - the normal idle screen's "Continuar" must never surface a daily
                # game (those live in their own world, resumed only through /daily's own status -
                # see docs/TODO/DAILY-GAMES.md §4.5).
                GameModel.daily_challenge_id.is_(None),
                filter_clause,
            )
            .order_by(GameModel.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        return self._row_to_game(game_row) if game_row is not None else None

    def get_recent_games(self, user_id: UUID, limit: int = 5) -> list[RecentGame]:
        """"Ver juegos" profile modal (roadmap #e) - a logged-in player's last `limit` games that
        reached a final state (finished naturally, or abandoned by starting a new one), most recent
        first. A game still actively in progress is intentionally excluded - it belongs on that
        mode's idle screen as "Continuar", not in this history list."""
        rows = self._session.execute(
            select(GameModel)
            .where(
                GameModel.user_id == user_id,
                or_(GameModel.finished.is_(True), GameModel.abandoned.is_(True)),
            )
            .order_by(GameModel.created_at.desc())
            .limit(limit)
        ).scalars().all()
        return [
            RecentGame(
                id=row.id,
                game_type=row.game_type,
                mode=row.mode,
                score=row.score,
                finished=row.finished,
                abandoned=row.abandoned,
                created_at=row.created_at,
                is_daily=row.daily_challenge_id is not None,
            )
            for row in rows
        ]

    def get_personal_records(self, owner: str, user_id: UUID | None) -> list[GameRecord]:
        """Roadmap point E - personal-best score per (game_type, mode), shown in the main menu.
        Filters by the account's user_id when logged in, otherwise by the anonymous browser's
        owner id - every game's score is higher-is-better (see games/shared/scoring.py's
        exp_decay_score and each game's win/streak-based deltas), so MAX(score) among finished
        games is a valid "best" for every existing game/mode."""
        filter_clause = GameModel.user_id == user_id if user_id is not None else GameModel.owner == owner
        rows = self._session.execute(
            select(GameModel.game_type, GameModel.mode, func.max(GameModel.score))
            .where(
                GameModel.finished.is_(True),
                # Roadmap #G - daily scores aren't comparable to normal play (different settings,
                # separate leaderboard - docs/TODO/DAILY-GAMES.md §4.5 [D]).
                GameModel.daily_challenge_id.is_(None),
                filter_clause,
            )
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
            .where(
                GameModel.game_type == game_type,
                GameModel.mode == mode,
                GameModel.finished.is_(True),
                # Roadmap #G - the normal leaderboard never mixes in daily scores; the daily
                # leaderboard is its own query scoped to one challenge (see
                # GamesService.get_daily_leaderboard, added in F5).
                GameModel.daily_challenge_id.is_(None),
            )
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

    def get_daily_leaderboard(self, game_type: str, mode: str, challenge_date: date) -> list[LeaderboardEntry]:
        """Roadmap #G, F5 - top 15 accounts by score for *one specific day's* challenge, not a
        rolling window like get_leaderboard's all/weekly/daily - a date with no challenge for this
        (game_type, mode) simply has no entries, not an error (docs/TODO/DAILY-GAMES.md §4.6)."""
        if (game_type, mode) not in _GAMES:
            raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")

        challenge_id = self._session.execute(
            select(DailyChallengeModel.id).where(
                DailyChallengeModel.challenge_date == challenge_date,
                DailyChallengeModel.game_type == game_type,
                DailyChallengeModel.mode == mode,
            )
        ).scalar_one_or_none()
        if challenge_id is None:
            return []

        best_score = func.max(GameModel.score).label("best_score")
        stmt = (
            select(UserModel.username, UserModel.skin_person_id, best_score)
            .join(UserModel, UserModel.id == GameModel.user_id)
            .where(GameModel.daily_challenge_id == challenge_id, GameModel.finished.is_(True))
            .group_by(UserModel.id, UserModel.username, UserModel.skin_person_id)
            .order_by(best_score.desc())
            .limit(15)
        )
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
        return self._row_to_game(game_row)

    def _row_to_game(self, game_row: GameModel) -> BaseGame:
        """Reconstructs a BaseGame from an already-fetched GameModel row - shared by _load_game
        (which also does the FOR UPDATE fetch + ownership check above) and get_current_game
        (roadmap #e), which needs the identical rounds/spec reconstruction but never locks the row
        since it isn't about to be played within this same request."""
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

        if game_row.daily_challenge_id is not None:
            # Roadmap #G - a daily game's class/kwargs come from its frozen challenge, not the live
            # settings/Immich queries every normal game uses (see _daily_game_kwargs).
            challenge = self._session.get(DailyChallengeModel, game_row.daily_challenge_id)
            if challenge is None:
                raise RuntimeError(f"game {game_row.id} references a missing daily challenge")
            game_class = _DAILY_GAME_CLASSES.get(game_row.game_type, spec.game_class)
            game = game_class(
                id=game_row.id,
                owner=game_row.owner,
                rounds=rounds,
                score=game_row.score,
                finished=game_row.finished,
                **self._daily_game_kwargs(game_row.game_type, game_row.mode, challenge, rounds_played=len(rounds)),
            )
            game.daily_challenge_date = challenge.challenge_date
            return game

        return spec.game_class(
            id=game_row.id,
            owner=game_row.owner,
            rounds=rounds,
            score=game_row.score,
            finished=game_row.finished,
            **self._game_kwargs(spec, game_row.game_type, game_row.mode),
        )

    def _abandon_active_games(
        self, owner: str, game_type: str, mode: str, user_id: UUID | None
    ) -> None:
        """Roadmap #e - marks every currently-active game of this same (owner-or-user, game_type,
        mode) as abandoned, right before a new one is created for it (see create_game). Marks
        *every* matching row rather than assuming there's ever only one - self-heals any stray
        unfinished game left over from before the `abandoned` column existed, or from the
        documented cross-tab race (two tabs both starting a new game for the same mode)."""
        filter_clause = GameModel.user_id == user_id if user_id is not None else GameModel.owner == owner
        rows = self._session.execute(
            select(GameModel).where(
                GameModel.game_type == game_type,
                GameModel.mode == mode,
                GameModel.finished.is_(False),
                GameModel.abandoned.is_(False),
                # Roadmap #G - critical: starting a normal game must never abandon an in-progress
                # daily of the same mode, and (create_daily_game, added in F3) creating a daily
                # must never abandon a normal game either - a daily challenge only ever gets one
                # game per player in the first place (docs/TODO/DAILY-GAMES.md §4.5).
                GameModel.daily_challenge_id.is_(None),
                filter_clause,
            )
        ).scalars().all()
        for row in rows:
            row.abandoned = True

    def _save_new_game(
        self, game: BaseGame, user_id: UUID | None = None, daily_challenge_id: UUID | None = None
    ) -> None:
        game_row = GameModel(
            id=game.id,
            owner=game.owner,
            user_id=user_id,
            game_type=game.game_type,
            mode=game.mode,
            score=game.score,
            finished=game.finished,
            daily_challenge_id=daily_challenge_id,
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
