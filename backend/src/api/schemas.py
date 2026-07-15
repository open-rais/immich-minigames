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

from domain.person import Person
from games.base import BaseGame, BaseRound
from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr import MODE_DAYS_TO_DATE, DateguessrRound
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS, LatLng, GeoguessrRound
from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle import MODE_PERSON, ImmichdleGame, ImmichdleRound
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import MODE_PERSON_ASSETS, MoreOrLessRound
from games.whos_that_person import GAME_TYPE as WHOS_THAT_PERSON_TYPE
from games.whos_that_person import MODE_NAMED_FACES, HiddenFace, WhosThatPersonRound
from services.games_service import UnsupportedGameError


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
            correct=round_.correct,
        )


class GeoguessrRoundOut(BaseModel):
    game_type: Literal["geoguessr"] = GEOGUESSR_TYPE
    id: UUID
    round_index: int
    # Main ("answer") asset first, then up to 4 decorative extras - see games/asset_rounds.py's
    # MAX_EXTRA_ASSETS. The guess/actual/score fields below are always about the main asset only.
    asset_ids: list[UUID]
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
            asset_ids=[round_.asset.id] + [extra.id for extra in round_.extras],
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
    # Main ("answer") asset first, then up to 4 decorative extras - see
    # GeoguessrRoundOut.asset_ids.
    asset_ids: list[UUID]
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
            asset_ids=[round_.asset.id] + [extra.id for extra in round_.extras],
            guess_date=round_.guess,
            actual_date=round_.asset.date if answered else None,
            days_off=round_.days_off if answered else None,
            score_delta=round_.score_delta if answered else None,
        )


class ImmichdleCluesOut(BaseModel):
    age: Literal["older", "younger", "same", "unknown"]
    asset_count: Literal["more", "less", "equal"]
    first_appearance: Literal["before", "after", "same", "unknown"]
    common_names: int
    ml_similarity: float | None
    assets_together: int
    age_close: bool | None
    first_appearance_close: bool | None
    asset_count_close: bool | None
    age_both_unknown: bool
    first_appearance_both_unknown: bool


class ImmichdleRoundOut(BaseModel):
    game_type: Literal["immichdle"] = IMMICHDLE_TYPE
    id: UUID
    round_index: int
    # Redacted (null) until this round has been answered - same rationale as
    # MoreOrLessRoundOut.candidate_asset_count. The target itself is never in a round's output at
    # all - see GameOut.target_person_id/name.
    guess_person_id: UUID | None
    guess_person_name: str | None
    guess_asset_count: int | None
    guess_birth_date: date | None
    guess_first_asset_date: date | None
    correct: bool | None
    clues: ImmichdleCluesOut | None

    @classmethod
    def from_round(cls, round_: ImmichdleRound) -> "ImmichdleRoundOut":
        answered = round_.answered
        guessed = round_.guessed_person if answered else None
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            guess_person_id=guessed.id if guessed else None,
            guess_person_name=guessed.name if guessed else None,
            guess_asset_count=guessed.asset_count if guessed else None,
            guess_birth_date=guessed.birth_date if guessed else None,
            guess_first_asset_date=guessed.first_asset_date if guessed else None,
            correct=round_.correct,
            clues=ImmichdleCluesOut(**round_.clues.to_dict()) if round_.clues else None,
        )


class HiddenFaceOut(BaseModel):
    face_id: UUID
    # Never secret - needed to draw the black box regardless of whether the round's been answered.
    image_width: int
    image_height: int
    bounding_box_x1: int
    bounding_box_y1: int
    bounding_box_x2: int
    bounding_box_y2: int
    # Redacted (null) until this round has been answered - same rationale as
    # MoreOrLessRoundOut.candidate_asset_count.
    person_id: UUID | None
    person_name: str | None
    correct: bool | None

    @classmethod
    def from_face(cls, face: HiddenFace, guess: UUID | None, answered: bool) -> "HiddenFaceOut":
        return cls(
            face_id=face.face_id,
            image_width=face.image_width,
            image_height=face.image_height,
            bounding_box_x1=face.bounding_box_x1,
            bounding_box_y1=face.bounding_box_y1,
            bounding_box_x2=face.bounding_box_x2,
            bounding_box_y2=face.bounding_box_y2,
            person_id=face.person_id if answered else None,
            person_name=face.person_name if answered else None,
            correct=(guess == face.person_id) if answered else None,
        )


class WhosThatPersonRoundOut(BaseModel):
    game_type: Literal["whos-that-person"] = WHOS_THAT_PERSON_TYPE
    id: UUID
    round_index: int
    asset_id: UUID
    faces: list[HiddenFaceOut]
    # Whether every hidden face in the round was guessed correctly - None until answered.
    correct: bool | None
    # Redacted (null) until this round has been answered - same rationale as
    # GeoguessrRoundOut.score_delta.
    score_delta: int | None

    @classmethod
    def from_round(cls, round_: WhosThatPersonRound) -> "WhosThatPersonRoundOut":
        answered = round_.answered
        guesses = round_.guess or {}
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            asset_id=round_.asset_id,
            faces=[HiddenFaceOut.from_face(face, guesses.get(face.face_id), answered) for face in round_.faces],
            score_delta=round_.score_delta,
            correct=round_.correct,
        )


RoundOut = Annotated[
    Union[MoreOrLessRoundOut, GeoguessrRoundOut, DateguessrRoundOut, ImmichdleRoundOut, WhosThatPersonRoundOut],
    Field(discriminator="game_type"),
]


def round_out_from_round(
    round_: BaseRound,
) -> MoreOrLessRoundOut | GeoguessrRoundOut | DateguessrRoundOut | ImmichdleRoundOut | WhosThatPersonRoundOut:
    if isinstance(round_, MoreOrLessRound):
        return MoreOrLessRoundOut.from_round(round_)
    if isinstance(round_, GeoguessrRound):
        return GeoguessrRoundOut.from_round(round_)
    if isinstance(round_, DateguessrRound):
        return DateguessrRoundOut.from_round(round_)
    if isinstance(round_, ImmichdleRound):
        return ImmichdleRoundOut.from_round(round_)
    if isinstance(round_, WhosThatPersonRound):
        return WhosThatPersonRoundOut.from_round(round_)
    raise TypeError(f"unsupported round type: {type(round_)}")


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


class ImmichdlePlayRoundIn(BaseModel):
    person_id: UUID

    def to_domain(self) -> UUID:
        return self.person_id


class WhosThatPersonPlayRoundIn(BaseModel):
    # face_id -> guessed person_id, one entry per hidden face in the round - WhosThatPersonGame
    # rejects an incomplete/mismatched mapping (see IncompleteGuessError), not this schema, since
    # what "complete" means depends on the round's own faces, not just the request body's shape.
    guesses: dict[UUID, UUID]

    def to_domain(self) -> dict[UUID, UUID]:
        return self.guesses


_PLAY_ROUND_SCHEMAS: dict[tuple[str, str], type[BaseModel]] = {
    (MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS): MoreOrLessPlayRoundIn,
    (GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS): GeoguessrPlayRoundIn,
    (DATEGUESSR_TYPE, MODE_DAYS_TO_DATE): DateguessrPlayRoundIn,
    (IMMICHDLE_TYPE, MODE_PERSON): ImmichdlePlayRoundIn,
    (WHOS_THAT_PERSON_TYPE, MODE_NAMED_FACES): WhosThatPersonPlayRoundIn,
}


def parse_guess(game_type: str, mode: str, body: dict[str, Any]) -> Any:
    """Picks the right guess schema for an already-known (game_type, mode) - the caller (see
    api/api.py's play_round) is expected to have looked the game up first, so this never needs the
    client to state its own game_type. Raises pydantic.ValidationError on a malformed body, and
    UnsupportedGameError (mapped to 400) if the (game_type, mode) pair has no schema - consistent
    with GamesService.create_game rather than surfacing a raw KeyError as a 500."""
    schema = _PLAY_ROUND_SCHEMAS.get((game_type, mode))
    if schema is None:
        raise UnsupportedGameError(f"unsupported game/mode: {game_type}/{mode}")
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
        correct = (
            answered_round.correct
            if isinstance(answered_round, (MoreOrLessRound, ImmichdleRound, WhosThatPersonRound))
            else None
        )
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
