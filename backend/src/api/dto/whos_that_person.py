"""Who'sThatPerson's request/response DTOs - see api/dto/__init__.py."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from games.whos_that_person import GAME_TYPE as WHOS_THAT_PERSON_TYPE
from games.whos_that_person import HiddenFace, WhosThatPersonRound


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


class WhosThatPersonPlayRoundIn(BaseModel):
    # face_id -> guessed person_id, one entry per hidden face in the round - WhosThatPersonGame
    # rejects an incomplete/mismatched mapping (see IncompleteGuessError), not this schema, since
    # what "complete" means depends on the round's own faces, not just the request body's shape.
    guesses: dict[UUID, UUID]

    def to_domain(self) -> dict[UUID, UUID]:
        return self.guesses
