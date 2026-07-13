"""
Pydantic request/response DTOs for the REST API - separate from the domain objects in
games/*.py. `RoundOut` is a discriminated union keyed by a `game_type` field the *server* sets (one
variant per game/mode) - this is the first second game, so the response shape generalizes here
instead of staying hardcoded to MoreOrLess. The request side (`parse_guess`) is deliberately not a
discriminated union: `game_id` already fixes a round's game/mode server-side (see api/api.py), so
asking the client to also echo back `game_type` in the guess body would be redundant - and worse, if
it disagreed with the game's actual type, nothing would catch the mismatch before it reached the
domain layer as a wrongly-shaped guess.
"""

from datetime import date
from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field

from games.base import BaseGame, BaseRound
from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr import MODE_DAYS_TO_DATE
from games.dateguessr import DateguessrRound
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS
from games.geoguessr import LatLng, GeoguessrRound
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import MODE_PERSON_ASSETS, MoreOrLessRound


class CreateGameIn(BaseModel):
    type: str
    mode: str


class MoreOrLessRoundOut(BaseModel):
    game_type: Literal["more-or-less"] = MORE_OR_LESS_TYPE
    id: UUID
    round_index: int
    reference_id: UUID
    reference_name: str
    reference_asset_count: int
    candidate_id: UUID
    candidate_name: str
    # Redacted (null) until this round has been answered - otherwise the correct answer could be
    # read straight out of the HTTP response before guessing.
    candidate_asset_count: int | None
    guess: Literal["more", "less"] | None
    correct: bool | None

    @classmethod
    def from_round(cls, round_: MoreOrLessRound) -> "MoreOrLessRoundOut":
        answered = round_.answered
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            reference_id=round_.reference.id,
            reference_name=round_.reference.name,
            reference_asset_count=round_.reference.asset_count,
            candidate_id=round_.candidate.id,
            candidate_name=round_.candidate.name,
            candidate_asset_count=round_.candidate.asset_count if answered else None,
            guess=round_.guess if answered else None,
            correct=(round_.score_delta == 1) if answered else None,
        )


class GeoguessrRoundOut(BaseModel):
    game_type: Literal["geoguessr"] = GEOGUESSR_TYPE
    id: UUID
    round_index: int
    asset_id: UUID
    guess_latitude: float | None
    guess_longitude: float | None
    # Redacted (null) until this round has been answered - same rationale as
    # MoreOrLessRoundOut.candidate_asset_count.
    actual_latitude: float | None
    actual_longitude: float | None
    distance_km: float | None
    score_delta: int | None

    @classmethod
    def from_round(cls, round_: GeoguessrRound) -> "GeoguessrRoundOut":
        answered = round_.answered
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            asset_id=round_.asset.id,
            guess_latitude=round_.guess.latitude if round_.guess else None,
            guess_longitude=round_.guess.longitude if round_.guess else None,
            actual_latitude=round_.asset.latitude if answered else None,
            actual_longitude=round_.asset.longitude if answered else None,
            distance_km=round(round_.distance_km, 3) if answered else None,
            score_delta=round_.score_delta if answered else None,
        )


class DateguessrRoundOut(BaseModel):
    game_type: Literal["dateguessr"] = DATEGUESSR_TYPE
    id: UUID
    round_index: int
    asset_id: UUID
    guess_date: date | None
    # Redacted (null) until this round has been answered - same rationale as
    # GeoguessrRoundOut.actual_latitude.
    actual_date: date | None
    days_off: int | None
    score_delta: int | None

    @classmethod
    def from_round(cls, round_: DateguessrRound) -> "DateguessrRoundOut":
        answered = round_.answered
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            asset_id=round_.asset.id,
            guess_date=round_.guess,
            actual_date=round_.asset.date if answered else None,
            days_off=round_.days_off if answered else None,
            score_delta=round_.score_delta if answered else None,
        )


RoundOut = Annotated[
    Union[MoreOrLessRoundOut, GeoguessrRoundOut, DateguessrRoundOut], Field(discriminator="game_type")
]


def round_out_from_round(round_: BaseRound) -> MoreOrLessRoundOut | GeoguessrRoundOut | DateguessrRoundOut:
    if isinstance(round_, MoreOrLessRound):
        return MoreOrLessRoundOut.from_round(round_)
    if isinstance(round_, GeoguessrRound):
        return GeoguessrRoundOut.from_round(round_)
    if isinstance(round_, DateguessrRound):
        return DateguessrRoundOut.from_round(round_)
    raise TypeError(f"unsupported round type: {type(round_)}")


class GameOut(BaseModel):
    id: UUID
    type: str
    mode: str
    score: int
    finished: bool
    rounds: list[RoundOut]

    @classmethod
    def from_game(cls, game: BaseGame) -> "GameOut":
        return cls(
            id=game.id,
            type=game.game_type,
            mode=game.mode,
            score=game.score,
            finished=game.finished,
            rounds=[round_out_from_round(r) for r in game.rounds],
        )


class MoreOrLessPlayRoundIn(BaseModel):
    guess: Literal["more", "less"]

    def to_domain(self) -> str:
        return self.guess


class GeoguessrPlayRoundIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    def to_domain(self) -> LatLng:
        return LatLng(latitude=self.latitude, longitude=self.longitude)


class DateguessrPlayRoundIn(BaseModel):
    date: date

    def to_domain(self) -> date:
        return self.date


_PLAY_ROUND_SCHEMAS: dict[tuple[str, str], type[BaseModel]] = {
    (MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS): MoreOrLessPlayRoundIn,
    (GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS): GeoguessrPlayRoundIn,
    (DATEGUESSR_TYPE, MODE_DAYS_TO_DATE): DateguessrPlayRoundIn,
}


def parse_guess(game_type: str, mode: str, body: dict[str, Any]) -> Any:
    """Picks the right guess schema for an already-known (game_type, mode) - the caller (see
    api/api.py's play_round) is expected to have looked the game up first, so this never needs the
    client to state its own game_type. Raises pydantic.ValidationError on a malformed body."""
    schema = _PLAY_ROUND_SCHEMAS[(game_type, mode)]
    return schema.model_validate(body).to_domain()


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
        correct = (answered_round.score_delta == 1) if isinstance(answered_round, MoreOrLessRound) else None
        return cls(
            correct=correct,
            score_delta=answered_round.score_delta,
            score=game.score,
            finished=game.finished,
            answered_round=round_out_from_round(answered_round),
            next_round=next_round,
        )
