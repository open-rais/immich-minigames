"""WhosThatPersonRound - a single blacked-out-faces round, its frozen face snapshots, and the
combo-streak scoring math that only the round itself needs. See games/whos_that_person/game.py for
the loop that drives rounds and games/whos_that_person/content.py for where a round's photo/faces
come from."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from domain.face import Face
from games.base import BaseRound
from games.shared.serialization import DictCodec


@dataclass(frozen=True)
class HiddenFace(DictCodec):
    """A blacked-out face's bounding box (never secret - needed to draw the box) plus the person it
    actually belongs to (secret until answered - redaction happens in the API DTO layer, not here) -
    frozen at round-creation time, same rationale as every other game's *Snapshot types."""

    face_id: UUID
    person_id: UUID
    person_name: str
    image_width: int
    image_height: int
    bounding_box_x1: int
    bounding_box_y1: int
    bounding_box_x2: int
    bounding_box_y2: int

    @classmethod
    def of(cls, face: Face) -> "HiddenFace":
        return cls(
            face_id=face.id,
            person_id=face.person_id,
            person_name=face.person_name,
            image_width=face.image_width,
            image_height=face.image_height,
            bounding_box_x1=face.bounding_box_x1,
            bounding_box_y1=face.bounding_box_y1,
            bounding_box_x2=face.bounding_box_x2,
            bounding_box_y2=face.bounding_box_y2,
        )


class WhosThatPersonRound(BaseRound):
    def __init__(
        self,
        id: UUID,
        game_id: UUID,
        round_index: int,
        asset_id: UUID,
        faces: list[HiddenFace],
        incoming_streak: int = 0,
    ) -> None:
        super().__init__(id, game_id, round_index, shown_entities=[asset_id] + [f.person_id for f in faces])
        self.asset_id = asset_id
        self.faces = faces
        self.guess: dict[UUID, UUID] | None = None  # face_id -> guessed person_id
        # person_id -> name, frozen at guess time by WhosThatPersonGame.play_round (roadmap #10's
        # rounds review, ROUNDS-VIEW.md §4.3) - same "snapshot" rationale as every other game's
        # *Snapshot types: the name the player *saw* shouldn't depend on Immich data staying put.
        # Empty (not None) for a round played before this field existed - see from_payload.
        self.guess_names: dict[UUID, str] = {}
        # Set at construction (the previous round's ending_streak, or 0 for the game's first
        # round) rather than injected later - see calculate_score().
        self.incoming_streak = incoming_streak
        self.ending_streak: int | None = None

    @property
    def results(self) -> list[bool]:
        """Per-face correctness, in self.faces order - the fixed order calculate_score() streaks
        over."""
        if self.guess is None:
            raise RuntimeError("results accessed before the round was answered")
        return [self.guess[face.face_id] == face.person_id for face in self.faces]

    @property
    def correct(self) -> bool | None:
        """Whether every hidden face in this round was guessed correctly - None until answered.
        Single definition of "correct" for the DTOs, same role as MoreOrLessRound.correct."""
        if not self.answered:
            return None
        return all(self.results)

    def calculate_score(self, settings: Mapping[str, float] | None = None) -> int:
        # No admin-configurable knob affects this game's scoring (only its length, see
        # WhosThatPersonGame's total_people/_max_hidden_faces) - settings is accepted only to
        # satisfy BaseRound's shared signature.
        results = self.results
        # A miss anywhere in this round zeroes the streak before any of the round's own hits are
        # scored - not just from the point of the miss onward (see games/whos_that_person/game.py's
        # module docstring).
        streak = self.incoming_streak if all(results) else 0
        delta = 0
        for is_correct in results:
            if is_correct:
                streak += 1
                delta += streak
            else:
                streak = 0
        self.ending_streak = streak
        return delta

    def to_payload(self) -> dict[str, Any]:
        return {
            "asset_id": str(self.asset_id),
            "faces": [f.to_dict() for f in self.faces],
            "guess": {str(k): str(v) for k, v in self.guess.items()} if self.guess is not None else None,
            "guess_names": {str(k): v for k, v in self.guess_names.items()},
            "incoming_streak": self.incoming_streak,
            "ending_streak": self.ending_streak,
        }

    @classmethod
    def from_payload(
        cls, id: UUID, game_id: UUID, round_index: int, payload: dict[str, Any], score_delta: int | None
    ) -> "WhosThatPersonRound":
        round_ = cls(
            id=id,
            game_id=game_id,
            round_index=round_index,
            asset_id=UUID(payload["asset_id"]),
            faces=[HiddenFace.from_dict(f) for f in payload["faces"]],
            incoming_streak=payload["incoming_streak"],
        )
        round_.guess = {UUID(k): UUID(v) for k, v in payload["guess"].items()} if payload["guess"] is not None else None
        # payload.get(...) or {} rather than payload["guess_names"] - a round played before this
        # field existed has no such key at all; it just shows "?" instead of a name in the "Tu
        # respuesta" rounds-review view (ROUNDS-VIEW.md §4.3), not a KeyError.
        round_.guess_names = {UUID(k): v for k, v in (payload.get("guess_names") or {}).items()}
        round_.ending_streak = payload["ending_streak"]
        round_.score_delta = score_delta
        return round_
