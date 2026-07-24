"""
Based on Who's That Pokémon. A photo is shown with some of its already-named detected faces blacked
out (up to MAX_HIDDEN_FACES) - the player identifies every blacked-out face before submitting. A
round is one photo: even when it hides several faces, they're all answered in a single submit, so
the round keeps the same one-guess shape every other game uses (see BaseRound.guess). The same
person can appear twice in one photo (mirrors, collages, etc.) - each hidden face is graded
independently against its own true person, never deduplicated. Faces without a name are never
blacked out (there'd be nothing to grade), so a photo can have more visible faces than hidden ones.
See docs/GAMES/WHOS_THAT_PERSON.md.

The game asks about TOTAL_PEOPLE people total, across as many rounds as it takes to reach that
count - a round's face count is capped so the running total never overshoots it.

Scoring is a combo streak counted by person, not by round: each correct guess adds the current
streak (which grows by 1 per consecutive hit); a wrong guess resets the streak to 0 for scoring
purposes. Crucially, that reset happens at the *start* of a round's score calculation whenever the
round contains any miss - not only from the point of the miss onward - so correct guesses that
happen to come before a miss within the same round don't get to spend a streak carried in from a
previous round (see WhosThatPersonRound.calculate_score).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from domain.face import Face
from games.base import BaseGame, BaseRound, PlayRoundResult
from games.serialization import DictCodec
from services.immich_service import ImmichService

GAME_TYPE = "whos-that-person"
MODE_NAMED_FACES = "namedFaces"

# Admin feature (ADMIN-FEATURE.md point #4) - public (no leading underscore) since
# services/game_settings.py imports these as defaults for the admin-configurable
# total_people/max_hidden_faces settings, same convention already used by e.g.
# asset_rounds.py's TOTAL_ROUNDS/MAX_SCORE.
TOTAL_PEOPLE = 15
MAX_HIDDEN_FACES = 5


class IncompleteGuessError(Exception):
    pass


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
        # scored - not just from the point of the miss onward (see module docstring).
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
        round_.guess = (
            {UUID(k): UUID(v) for k, v in payload["guess"].items()} if payload["guess"] is not None else None
        )
        round_.ending_streak = payload["ending_streak"]
        round_.score_delta = score_delta
        return round_


class WhosThatPersonGame(BaseGame):
    def __init__(
        self,
        id: UUID,
        owner: str,
        rounds: list[WhosThatPersonRound],
        immich_service: ImmichService,
        score: int = 0,
        finished: bool = False,
        settings: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            owner=owner,
            game_type=GAME_TYPE,
            mode=MODE_NAMED_FACES,
            rounds=rounds,
            score=score,
            finished=finished,
            settings=settings,
        )
        self._immich_service = immich_service

    @property
    def _people_asked(self) -> int:
        return sum(len(round_.faces) for round_ in self.rounds)

    # -- admin-configurable (ADMIN-FEATURE.md point #4, see services/game_settings.py) ----------

    @property
    def total_people(self) -> int:
        # Public (no leading underscore) - api/dto/common.py's GameOut reads this to show the
        # frontend the *live* total instead of the hardcoded display-only constant it used to
        # mirror.
        return int(self._settings.get("total_people", TOTAL_PEOPLE))

    @property
    def _max_hidden_faces(self) -> int:
        return int(self._settings.get("max_hidden_faces", MAX_HIDDEN_FACES))

    @property
    def _shown_asset_ids(self) -> frozenset[UUID]:
        # Never repeat the same photo within a game (unlike people, who can and will repeat across
        # photos - the named-people pool is much smaller than 15).
        return frozenset(round_.asset_id for round_ in self.rounds)

    @classmethod
    def start(
        cls, id: UUID, owner: str, immich_service: ImmichService, settings: Mapping[str, float] | None = None
    ) -> "WhosThatPersonGame":
        total_people = int((settings or {}).get("total_people", TOTAL_PEOPLE))
        max_hidden_faces = int((settings or {}).get("max_hidden_faces", MAX_HIDDEN_FACES))
        faces = immich_service.get_random_asset_with_named_faces(max_faces=min(max_hidden_faces, total_people))
        if not faces:
            raise ValueError("not enough named faces in Immich to start a Who'sThatPerson game")

        first_round = WhosThatPersonRound(
            id=uuid4(),
            game_id=id,
            round_index=1,
            asset_id=faces[0].asset_id,
            faces=[HiddenFace.of(f) for f in faces],
        )
        return cls(id=id, owner=owner, rounds=[first_round], immich_service=immich_service, settings=settings)

    def play_round(self, guess: dict[UUID, UUID]) -> PlayRoundResult:
        if self.finished:
            raise ValueError("game is already finished")
        expected_face_ids = {face.face_id for face in self.current_round.faces}
        if set(guess) != expected_face_ids:
            raise IncompleteGuessError("guess must include exactly one entry per hidden face in the round")
        return super().play_round(guess)

    def has_next_round(self) -> bool:
        if self._people_asked >= self.total_people:
            return False
        max_faces = min(self._max_hidden_faces, self.total_people - self._people_asked)
        # Cheap-ish existence check, discarded - create_next_round() samples again, same
        # double-sample pattern MoreOrLessGame/AssetRoundsGame already use.
        candidate = self._immich_service.get_random_asset_with_named_faces(
            max_faces=max_faces, exclude_asset_ids=self._shown_asset_ids
        )
        return bool(candidate)

    def create_next_round(self) -> WhosThatPersonRound:
        previous = self.current_round
        max_faces = min(self._max_hidden_faces, self.total_people - self._people_asked)
        faces = self._immich_service.get_random_asset_with_named_faces(
            max_faces=max_faces, exclude_asset_ids=self._shown_asset_ids
        )
        if not faces:
            raise ValueError("no more eligible photos left - has_next_round() should have returned False")

        if previous.ending_streak is None:
            raise RuntimeError("create_next_round() called before calculate_score() set ending_streak")
        return WhosThatPersonRound(
            id=uuid4(),
            game_id=self.id,
            round_index=previous.round_index + 1,
            asset_id=faces[0].asset_id,
            faces=[HiddenFace.of(f) for f in faces],
            incoming_streak=previous.ending_streak,
        )
