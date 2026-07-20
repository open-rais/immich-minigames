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
from services.games_service import GameRecord, LeaderboardEntry, UnsupportedGameError


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
    # Admin feature (ADMIN-FEATURE.md point #4) - the *live* configured total for this game
    # instance (AssetRoundsGame.total_rounds / WhosThatPersonGame.total_people), so the frontend's
    # round counter (e.g. "Round 2 of 5") reflects an admin override instead of a hardcoded
    # display-only constant. Null for every other game, which has no such fixed/counted total.
    total_rounds: int | None = None
    total_people: int | None = None

    @classmethod
    def from_game(cls, game: BaseGame) -> "GameOut":
        target_id = None
        target_name = None
        if isinstance(game, ImmichdleGame) and game.finished:
            target_id = game.target.id
            target_name = game.target.name
        return cls(
            id=game.id,
            type=game.game_type,
            mode=game.mode,
            score=game.score,
            finished=game.finished,
            rounds=[round_out_from_round(r) for r in game.rounds],
            target_person_id=target_id,
            target_person_name=target_name,
            total_rounds=game.total_rounds if isinstance(game, AssetRoundsGame) else None,
            total_people=game.total_people if isinstance(game, WhosThatPersonGame) else None,
        )


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


# -- admin game settings (ADMIN-FEATURE.md point #4, see services/game_settings.py) ---


class GameSettingOut(BaseModel):
    key: str
    value: float
    default: float
    value_type: Literal["int", "float"]
    min_value: float


class GameSettingsOut(BaseModel):
    game_type: str
    settings: list[GameSettingOut]

    @classmethod
    def from_specs(cls, game_type: str, specs: list[SettingSpec], values: dict[str, float]) -> "GameSettingsOut":
        return cls(
            game_type=game_type,
            settings=[
                GameSettingOut(
                    key=spec.key,
                    value=values[spec.key],
                    default=spec.default,
                    value_type=spec.value_type,
                    min_value=spec.min_value,
                )
                for spec in specs
            ],
        )
