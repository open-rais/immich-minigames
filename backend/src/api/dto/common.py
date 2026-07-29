"""DTOs and glue shared across every game - see api/dto/__init__.py. `RoundOut` is a discriminated
union keyed by a `game_type` field the *server* sets (one variant per game/mode) - this is the
first second game, so the response shape generalizes here instead of staying hardcoded to
MoreOrLess. The request side (`parse_guess`) is deliberately not a discriminated union: `game_id`
already fixes a round's game/mode server-side (see api/api.py), so asking the client to also echo
back `game_type` in the guess body would be redundant - and worse, if it disagreed with the game's
actual type, nothing would catch the mismatch before it reached the domain layer as a
wrongly-shaped guess.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field

from api.dto.dateguessr import DateguessrPlayRoundIn, DateguessrRoundOut
from api.dto.geoguessr import GeoguessrPlayRoundIn, GeoguessrRoundOut
from api.dto.immichdle import ImmichdlePlayRoundIn, ImmichdleRoundOut
from api.dto.more_or_less import MoreOrLessPlayRoundIn, MoreOrLessRoundOut
from api.dto.whos_that_person import WhosThatPersonPlayRoundIn, WhosThatPersonRoundOut
from domain.person import Person
from games.asset_rounds import AssetRoundsGame
from games.base import BaseGame, BaseRound
from games.dateguessr import DateguessrRound
from games.geoguessr import GeoguessrRound
from games.immichdle import ImmichdleGame, ImmichdleRound
from games.more_or_less import MoreOrLessRound
from games.whos_that_person import WhosThatPersonGame, WhosThatPersonRound
from services.game_settings import SettingSpec
from services.games_service import DailyModeStatus, GameRecord, LeaderboardEntry, RecentGame, UnsupportedGameError


class CreateGameIn(BaseModel):
    type: str
    mode: str


RoundOut = Annotated[
    Union[MoreOrLessRoundOut, GeoguessrRoundOut, DateguessrRoundOut, ImmichdleRoundOut, WhosThatPersonRoundOut],
    Field(discriminator="game_type"),
]


@dataclass(frozen=True)
class _RoundSpec:
    """One registry entry per concrete Round class - single source of truth for what this API
    layer needs per game (used to be three separate structures that had to stay in sync: a
    (game_type, mode)-keyed guess-schema dict here, an isinstance ladder in round_out_from_round
    picking the right *RoundOut DTO, and another isinstance check in PlayRoundOut.from_answered for
    whether "correct" is even a meaningful concept for this game)."""

    guess_schema: type[BaseModel]
    out_class: type[BaseModel]
    # Whether this round type has a meaningful pass/fail "correct" (MoreOrLess/Immichdle/
    # WhosThatPerson) vs. a continuous score with no such concept (Geoguessr/Dateguessr).
    has_binary_correctness: bool


_ROUND_SPECS: dict[type[BaseRound], _RoundSpec] = {
    MoreOrLessRound: _RoundSpec(MoreOrLessPlayRoundIn, MoreOrLessRoundOut, has_binary_correctness=True),
    GeoguessrRound: _RoundSpec(GeoguessrPlayRoundIn, GeoguessrRoundOut, has_binary_correctness=False),
    DateguessrRound: _RoundSpec(DateguessrPlayRoundIn, DateguessrRoundOut, has_binary_correctness=False),
    ImmichdleRound: _RoundSpec(ImmichdlePlayRoundIn, ImmichdleRoundOut, has_binary_correctness=True),
    WhosThatPersonRound: _RoundSpec(
        WhosThatPersonPlayRoundIn, WhosThatPersonRoundOut, has_binary_correctness=True
    ),
}


def _round_spec(round_: BaseRound) -> _RoundSpec:
    spec = _ROUND_SPECS.get(type(round_))
    if spec is None:
        raise UnsupportedGameError(f"unsupported round type: {type(round_).__name__}")
    return spec


def round_out_from_round(
    round_: BaseRound,
) -> MoreOrLessRoundOut | GeoguessrRoundOut | DateguessrRoundOut | ImmichdleRoundOut | WhosThatPersonRoundOut:
    return _round_spec(round_).out_class.from_round(round_)


def parse_guess(round_: BaseRound, body: dict[str, Any]) -> Any:
    """Picks the right guess schema for an already-loaded round - the caller (see api/api.py's
    play_round) has already looked the game up (and confirmed this is the pending round), so this
    never needs the client to also restate its own game_type in the guess body. Raises
    pydantic.ValidationError on a malformed body."""
    return _round_spec(round_).guess_schema.model_validate(body).to_domain()


class GameOut(BaseModel):
    id: UUID
    type: str
    mode: str
    score: int
    finished: bool
    rounds: list[RoundOut]
    # Only ever populated for a finished Immichdle game (see ImmichdleGame.target) - the mystery
    # person is revealed once the game is over, win or lose. Null for every other game/mode and for
    # an Immichdle game still in progress, where revealing it would be a straight cheat.
    target_person_id: UUID | None = None
    target_person_name: str | None = None
    # Roadmap #10 (rounds review) - the target row in the post-game GuessTable (ROUNDS-VIEW.md §4.6).
    # Same redaction condition as target_person_id/name above - PersonSnapshot already carries these,
    # just not previously surfaced here.
    target_asset_count: int | None = None
    target_birth_date: date | None = None
    target_first_asset_date: date | None = None
    # Admin feature (ADMIN-FEATURE.md point #4) - the *live* configured total for this game
    # instance (AssetRoundsGame.total_rounds / WhosThatPersonGame.total_people), so the frontend's
    # round counter (e.g. "Round 2 of 5") reflects an admin override instead of a hardcoded
    # display-only constant. Null for every other game, which has no such fixed/counted total.
    total_rounds: int | None = None
    total_people: int | None = None
    # Roadmap #G - set only for a daily-challenge game (see games/base.py's BaseGame.
    # daily_challenge_date), null for every normal game. Lets the frontend tell a resumed/loaded
    # game is a daily one on a fresh page load (no separate "Nuevo juego" affordance, no re-offer
    # to play) and titles the rounds-review page (docs/TODO/DAILY-GAMES.md §5).
    daily_challenge_date: date | None = None

    @classmethod
    def from_game(cls, game: BaseGame) -> "GameOut":
        target_id = None
        target_name = None
        target_asset_count = None
        target_birth_date = None
        target_first_asset_date = None
        if isinstance(game, ImmichdleGame) and game.finished:
            target_id = game.target.id
            target_name = game.target.name
            target_asset_count = game.target.asset_count
            target_birth_date = game.target.birth_date
            target_first_asset_date = game.target.first_asset_date
        return cls(
            id=game.id,
            type=game.game_type,
            mode=game.mode,
            score=game.score,
            finished=game.finished,
            rounds=[round_out_from_round(r) for r in game.rounds],
            target_person_id=target_id,
            target_person_name=target_name,
            target_asset_count=target_asset_count,
            target_birth_date=target_birth_date,
            target_first_asset_date=target_first_asset_date,
            total_rounds=game.total_rounds if isinstance(game, AssetRoundsGame) else None,
            total_people=game.total_people if isinstance(game, WhosThatPersonGame) else None,
            daily_challenge_date=game.daily_challenge_date,
        )


# -- resumable games (roadmap point #e, see GamesService.get_current_game/get_recent_games) ---


class CurrentGameOut(BaseModel):
    # A wrapper, not a 404 - "no active game" is the expected result on every idle-screen visit,
    # not an error the frontend needs to distinguish from a real failure.
    game: GameOut | None

    @classmethod
    def from_game(cls, game: BaseGame | None) -> "CurrentGameOut":
        return cls(game=GameOut.from_game(game) if game is not None else None)


class RecentGameOut(BaseModel):
    id: UUID
    game_type: str
    mode: str
    score: int
    finished: bool
    abandoned: bool
    created_at: datetime
    # Roadmap #G - whether this was a daily-challenge game (see GamesService.get_recent_games).
    is_daily: bool

    @classmethod
    def from_recent_game(cls, recent: RecentGame) -> "RecentGameOut":
        return cls(
            id=recent.id,
            game_type=recent.game_type,
            mode=recent.mode,
            score=recent.score,
            finished=recent.finished,
            abandoned=recent.abandoned,
            created_at=recent.created_at,
            is_daily=recent.is_daily,
        )


class RecentGamesOut(BaseModel):
    games: list[RecentGameOut]

    @classmethod
    def from_recent_games(cls, games: list[RecentGame]) -> "RecentGamesOut":
        return cls(games=[RecentGameOut.from_recent_game(g) for g in games])


class PlayRoundOut(BaseModel):
    # Binary-guess concept (MoreOrLess) - null for games with a continuous score (Geoguessr).
    correct: bool | None
    score_delta: int
    score: int
    finished: bool
    # The just-answered round, now with its answer revealed - lets the frontend show it without a
    # follow-up GET /games/{id} just to read the revealed fields.
    answered_round: RoundOut
    next_round: RoundOut | None

    @classmethod
    def from_answered(cls, game: BaseGame, answered_round: BaseRound) -> "PlayRoundOut":
        next_round = None if game.finished else round_out_from_round(game.current_round)
        correct = answered_round.correct if _round_spec(answered_round).has_binary_correctness else None
        return cls(
            correct=correct,
            score_delta=answered_round.score_delta,
            score=game.score,
            finished=game.finished,
            answered_round=round_out_from_round(answered_round),
            next_round=next_round,
        )


# -- person search (reusable across features - not game-specific, see api.py's /persons/search) ---


class PersonSearchResultOut(BaseModel):
    id: UUID
    name: str

    @classmethod
    def from_person(cls, person: Person) -> "PersonSearchResultOut":
        return cls(id=person.id, name=person.name)


class PersonSearchOut(BaseModel):
    results: list[PersonSearchResultOut]

    @classmethod
    def from_persons(cls, persons: list[Person]) -> "PersonSearchOut":
        return cls(results=[PersonSearchResultOut.from_person(p) for p in persons])


# -- personal records (roadmap point E, see GamesService.get_personal_records) ---


class GameRecordOut(BaseModel):
    game_type: str
    mode: str
    best_score: int

    @classmethod
    def from_record(cls, record: GameRecord) -> "GameRecordOut":
        return cls(game_type=record.game_type, mode=record.mode, best_score=record.best_score)


class GameRecordsOut(BaseModel):
    records: list[GameRecordOut]

    @classmethod
    def from_records(cls, records: list[GameRecord]) -> "GameRecordsOut":
        return cls(records=[GameRecordOut.from_record(r) for r in records])


# -- leaderboard (roadmap point F, see GamesService.get_leaderboard) ---

LeaderboardWindow = Literal["all", "weekly", "daily"]


class LeaderboardEntryOut(BaseModel):
    rank: int
    username: str
    skin_person_id: UUID | None
    best_score: int

    @classmethod
    def from_entry(cls, entry: LeaderboardEntry) -> "LeaderboardEntryOut":
        return cls(
            rank=entry.rank,
            username=entry.username,
            skin_person_id=entry.skin_person_id,
            best_score=entry.best_score,
        )


class LeaderboardOut(BaseModel):
    window: LeaderboardWindow
    entries: list[LeaderboardEntryOut]

    @classmethod
    def from_entries(cls, window: LeaderboardWindow, entries: list[LeaderboardEntry]) -> "LeaderboardOut":
        return cls(window=window, entries=[LeaderboardEntryOut.from_entry(e) for e in entries])


# -- daily leaderboard (roadmap point #G, F5 - see GamesService.get_daily_leaderboard) ---


class DailyLeaderboardOut(BaseModel):
    date: date
    entries: list[LeaderboardEntryOut]

    @classmethod
    def from_entries(cls, challenge_date: date, entries: list[LeaderboardEntry]) -> "DailyLeaderboardOut":
        return cls(date=challenge_date, entries=[LeaderboardEntryOut.from_entry(e) for e in entries])


# -- admin game settings (ADMIN-FEATURE.md point #4, see services/game_settings.py) ---


class GameSettingOut(BaseModel):
    key: str
    value: float
    default: float
    value_type: Literal["int", "float"]
    min_value: float
    max_value: float


class GameSettingsOut(BaseModel):
    game_type: str
    mode: str
    settings: list[GameSettingOut]

    @classmethod
    def from_specs(
        cls, game_type: str, mode: str, specs: list[SettingSpec], values: dict[str, float]
    ) -> "GameSettingsOut":
        return cls(
            game_type=game_type,
            mode=mode,
            settings=[
                GameSettingOut(
                    key=spec.key,
                    value=values[spec.key],
                    default=spec.default,
                    value_type=spec.value_type,
                    min_value=spec.min_value,
                    max_value=spec.max_value,
                )
                for spec in specs
            ],
        )


# -- daily games admin config (roadmap point #G, see services/daily_settings.py) ---


class DailySettingsOut(BaseModel):
    game_type: str
    mode: str
    # The "Activar juego diario" checkbox from roadmap #f - whether this mode is offered in the
    # daily rotation at all.
    enabled: bool
    settings: list[GameSettingOut]

    @classmethod
    def from_specs(
        cls, game_type: str, mode: str, enabled: bool, specs: list[SettingSpec], values: dict[str, float]
    ) -> "DailySettingsOut":
        return cls(
            game_type=game_type,
            mode=mode,
            enabled=enabled,
            settings=[
                GameSettingOut(
                    key=spec.key,
                    value=values[spec.key],
                    default=spec.default,
                    value_type=spec.value_type,
                    min_value=spec.min_value,
                    max_value=spec.max_value,
                )
                for spec in specs
            ],
        )


class UpdateDailySettingsIn(BaseModel):
    # PATCH semantics - omit a field to leave it unchanged (mirrors auth_schemas.py's
    # UpdateProfileIn), so toggling "enabled" from the admin UI doesn't require also restating
    # every setting value, and saving settings doesn't require also restating "enabled".
    enabled: bool | None = None
    values: dict[str, float] | None = None


# -- daily games player-facing status (roadmap point #G, see services/games_service.py's
# GamesService.get_daily_status/create_daily_game) ---

DailyModeStatusValue = Literal["not_played", "in_progress", "finished"]


class DailyModeStatusOut(BaseModel):
    game_type: str
    mode: str
    status: DailyModeStatusValue
    game_id: UUID | None
    score: int | None

    @classmethod
    def from_status(cls, status: DailyModeStatus) -> "DailyModeStatusOut":
        return cls(
            game_type=status.game_type,
            mode=status.mode,
            status=status.status,
            game_id=status.game_id,
            score=status.score,
        )


class DailyStatusOut(BaseModel):
    # ISO datetimes (server time, decision [G]) - the frontend's countdown ticks off the offset
    # between these two rather than trusting its own clock alone (docs/TODO/DAILY-GAMES.md §4.7).
    resets_at: datetime
    server_now: datetime
    modes: list[DailyModeStatusOut]

    @classmethod
    def from_statuses(cls, resets_at: datetime, server_now: datetime, statuses: list[DailyModeStatus]) -> "DailyStatusOut":
        return cls(
            resets_at=resets_at, server_now=server_now, modes=[DailyModeStatusOut.from_status(s) for s in statuses]
        )


# -- public runtime config (ROUNDS-VIEW.md roadmap point #10, see Settings.immich_public_url) ---


class ConfigOut(BaseModel):
    # Settings.immich_public_url, already resolved (IMMICH_EXTERNAL_URL or a fallback to
    # IMMICH_SERVER_URL) - optional because immich_server_url is a plain str field with no
    # guarantee against being blanked out, not because callers are expected to see null in practice.
    immich_external_url: str | None
