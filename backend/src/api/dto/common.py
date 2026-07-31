"""DTOs and glue shared across every game - see api/dto/__init__.py. `RoundOut` is a discriminated
union keyed by a `game_type` field the *server* sets (one variant per game/mode) - this is the
first second game, so the response shape generalizes here instead of staying hardcoded to
MoreOrLess. The request side (`parse_guess`) is deliberately not a discriminated union: `game_id`
already fixes a round's game/mode server-side (see api/api.py), so asking the client to also echo
back `game_type` in the guess body would be redundant - and worse, if it disagreed with the game's
actual type, nothing would catch the mismatch before it reached the domain layer as a
wrongly-shaped guess.

Everything that doesn't spread across every game/mode lives in a sibling module instead
(api/dto/persons.py, records.py, leaderboard.py, daily.py, admin.py, config.py), keeping this file
scoped to what's genuinely cross-game.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field

from api.dto.dateguessr import DateguessrPlayRoundIn, DateguessrRoundOut
from api.dto.geoguessr import GeoguessrPlayRoundIn, GeoguessrRoundOut
from api.dto.immichdle import ImmichdlePlayRoundIn, ImmichdleRoundOut
from api.dto.more_or_less import MoreOrLessPlayRoundIn, MoreOrLessRoundOut
from api.dto.timeline import TimelinePlayRoundIn, TimelineRoundOut
from api.dto.whos_that_person import WhosThatPersonPlayRoundIn, WhosThatPersonRoundOut
from games.base import BaseGame, BaseRound
from games.dateguessr import DateguessrRound
from games.geoguessr import GeoguessrRound
from games.immichdle import ImmichdleGame, ImmichdleRound
from games.more_or_less import MoreOrLessRound
from games.timeline import TimelineRound
from games.whos_that_person import WhosThatPersonRound
from services.errors import UnsupportedGameError
from services.scores_service import RecentGame


class CreateGameIn(BaseModel):
    type: str
    mode: str


RoundOut = Annotated[
    MoreOrLessRoundOut
    | GeoguessrRoundOut
    | DateguessrRoundOut
    | ImmichdleRoundOut
    | WhosThatPersonRoundOut
    | TimelineRoundOut,
    Field(discriminator="game_type"),
]


@dataclass(frozen=True)
class _RoundSpec:
    """One registry entry per concrete Round class - single source of truth for what this API
    layer needs per game, avoiding three separate structures that would otherwise have to stay in
    sync: a (game_type, mode)-keyed guess-schema dict here, an isinstance ladder in
    round_out_from_round picking the right *RoundOut DTO, and another isinstance check in
    PlayRoundOut.from_answered for whether "correct" is even a meaningful concept for this game."""

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
    WhosThatPersonRound: _RoundSpec(WhosThatPersonPlayRoundIn, WhosThatPersonRoundOut, has_binary_correctness=True),
    TimelineRound: _RoundSpec(TimelinePlayRoundIn, TimelineRoundOut, has_binary_correctness=True),
}


def _round_spec(round_: BaseRound) -> _RoundSpec:
    spec = _ROUND_SPECS.get(type(round_))
    if spec is None:
        raise UnsupportedGameError(f"unsupported round type: {type(round_).__name__}")
    return spec


def round_out_from_round(
    round_: BaseRound,
) -> (
    MoreOrLessRoundOut
    | GeoguessrRoundOut
    | DateguessrRoundOut
    | ImmichdleRoundOut
    | WhosThatPersonRoundOut
    | TimelineRoundOut
):
    return _round_spec(round_).out_class.from_round(round_)


def parse_guess(round_: BaseRound, body: dict[str, Any]) -> Any:
    """Picks the right guess schema for an already-loaded round - the caller (see api/api.py's
    play_round) has already looked the game up (and confirmed this is the pending round), so this
    never needs the client to also restate its own game_type in the guess body. The round itself is
    passed through as pydantic's `context` so a schema that needs it (TimelinePlayRoundIn's
    board-length upper bound) can validate against it - every other schema simply ignores it. Raises
    pydantic.ValidationError on a malformed body."""
    return _round_spec(round_).guess_schema.model_validate(body, context={"round": round_}).to_domain()


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
    # The target row in the post-game GuessTable. Same redaction condition as target_person_id/name
    # above - PersonSnapshot already carries these; surfaced here too for that table.
    target_asset_count: int | None = None
    target_birth_date: date | None = None
    target_first_asset_date: date | None = None
    # The *live* configured total for this game
    # instance (BaseGame.total_rounds/total_people, overridden by Geoguessr/Dateguessr and
    # WhosThatPerson respectively), so the frontend's round counter (e.g. "Round 2 of 5") reflects
    # an admin override instead of a hardcoded display-only constant. Null for every other game,
    # which has no such fixed/counted total.
    total_rounds: int | None = None
    total_people: int | None = None
    # Set only for a daily-challenge game (see games/base.py's BaseGame.
    # daily_challenge_date), null for every normal game. Lets the frontend tell a resumed/loaded
    # game is a daily one on a fresh page load (no separate "Nuevo juego" affordance, no re-offer
    # to play) and titles the rounds-review page.
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
            total_rounds=game.total_rounds,
            total_people=game.total_people,
            daily_challenge_date=game.daily_challenge_date,
        )


# -- resumable games (see GamesService.get_current_game/get_recent_games) ---


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
    # Whether this was a daily-challenge game (see GamesService.get_recent_games).
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
