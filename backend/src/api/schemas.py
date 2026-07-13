"""
Pydantic request/response DTOs for the REST API - separate from the domain objects in
games/*.py. Coupled to MoreOrLess's round shape (reference/candidate persons) for now, since
that's the only game/mode this API serves - will need to generalize once a second game is added.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from games.base import BaseGame, BaseRound
from games.more_or_less import MoreOrLessRound


class CreateGameIn(BaseModel):
    type: str
    mode: str


class RoundOut(BaseModel):
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
    def from_round(cls, round_: MoreOrLessRound) -> "RoundOut":
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
            rounds=[RoundOut.from_round(r) for r in game.rounds],
        )


class PlayRoundIn(BaseModel):
    guess: Literal["more", "less"]


class PlayRoundOut(BaseModel):
    correct: bool
    score_delta: int
    score: int
    finished: bool
    # The just-answered round, now with candidate_asset_count revealed - lets the frontend show
    # the revealed count without a follow-up GET /games/{id} just to read one field.
    answered_round: RoundOut
    next_round: RoundOut | None

    @classmethod
    def from_answered(cls, game: BaseGame, answered_round: BaseRound) -> "PlayRoundOut":
        next_round = None if game.finished else RoundOut.from_round(game.current_round)
        return cls(
            correct=answered_round.score_delta == 1,
            score_delta=answered_round.score_delta,
            score=game.score,
            finished=game.finished,
            answered_round=RoundOut.from_round(answered_round),
            next_round=next_round,
        )
