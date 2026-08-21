"""TriviumRound - a single multiple-choice round: one question (subject + render params + 4
alternatives + which is correct + what media to show, all built by a games/trivium/questions/
QuestionType) plus the frontend-reported answer time. See games/trivium/game.py for the loop that
drives rounds. Scoring is linear by elapsed time (calculate_score below); the backend trusts
`elapsed_ms` as reported by the frontend, only clamping it - this is a self-hosted app for
family/private use, not a competitive public ranking, so simplicity wins over anti-cheat."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from games.base import BaseRound
from games.trivium.questions.base import GeneratedQuestion, MediaSpec

# Defaults for the two admin-configurable knobs the scoring formula reads (games/trivium/
# settings.py) - see calculate_score below (e.g. 100 pts / 10s -> 50 pts at 5s elapsed).
MAX_POINTS = 100
ANSWER_TIME_SECONDS = 10


@dataclass(frozen=True)
class Answer:
    """What the player submits for a round - see api/dto/trivium.py's TriviumPlayRoundIn.
    `alternative` is null on a timeout: not answering within answer_time_seconds counts as an
    incorrect answer that ends the game, not a 0-point round that lets the game continue -
    `elapsed_ms` is still reported on a wrong/timed-out guess too, purely for a future
    rounds-review screen, since a wrong answer always scores 0 regardless of its value."""

    alternative: int | None
    elapsed_ms: int


def _media_to_payload(media: MediaSpec) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": media.kind}
    if media.asset_id is not None:
        payload["asset_id"] = str(media.asset_id)
    if media.person_id is not None:
        payload["person_id"] = str(media.person_id)
    if media.person_ids is not None:
        payload["person_ids"] = [str(p) for p in media.person_ids]
    return payload


def _media_from_payload(payload: dict[str, Any]) -> MediaSpec:
    return MediaSpec(
        kind=payload["kind"],
        asset_id=UUID(payload["asset_id"]) if "asset_id" in payload else None,
        person_id=UUID(payload["person_id"]) if "person_id" in payload else None,
        person_ids=[UUID(p) for p in payload["person_ids"]] if "person_ids" in payload else None,
    )


class TriviumRound(BaseRound):
    def __init__(
        self,
        id: UUID,
        game_id: UUID,
        round_index: int,
        question_kind: str,
        subject_id: UUID,
        params: dict[str, Any],
        alternatives: list[Any],
        correct_index: int,
        media: MediaSpec,
    ) -> None:
        super().__init__(id, game_id, round_index, shown_entities=[subject_id])
        self.question_kind = question_kind
        self.subject_id = subject_id
        self.params = params
        self.alternatives = alternatives
        self.correct_index = correct_index
        self.media = media
        self.guess: Answer | None = None

    @classmethod
    def of(cls, id: UUID, game_id: UUID, round_index: int, question: GeneratedQuestion) -> "TriviumRound":
        return cls(
            id=id,
            game_id=game_id,
            round_index=round_index,
            question_kind=question.question_kind,
            subject_id=question.subject_id,
            params=question.params,
            alternatives=question.alternatives,
            correct_index=question.correct_index,
            media=question.media,
        )

    @property
    def correct(self) -> bool | None:
        """Whether the chosen alternative was the right one - None until answered, False (not an
        error) for a timeout (`guess.alternative is None`). Single definition of "correct" for the
        DTOs, same role as MoreOrLessRound.correct - deliberately independent of score_delta, since
        a correct answer given right at the time limit still scores 0 (see calculate_score) but
        must still count as a win for has_next_round()."""
        if not self.answered:
            return None
        assert self.guess is not None
        return self.guess.alternative == self.correct_index

    def calculate_score(self, settings: Mapping[str, float] | None = None) -> int:
        if not self.correct:
            return 0
        assert self.guess is not None
        settings = settings or {}
        max_points = settings.get("max_points", MAX_POINTS)
        answer_time_ms = settings.get("answer_time_seconds", ANSWER_TIME_SECONDS) * 1000
        # The clamp: negative elapsed (a suspended device, a clock change) counts as instant (max
        # score); anything past the limit counts as the limit (0 score). Not anti-cheat - see the
        # module docstring - just a safety net against clocks/lag/throttled background timers.
        elapsed_ms = max(0, min(self.guess.elapsed_ms, answer_time_ms))
        return round(max_points * (1 - elapsed_ms / answer_time_ms))

    def to_payload(self) -> dict[str, Any]:
        return {
            "question_kind": self.question_kind,
            "subject_id": str(self.subject_id),
            "params": self.params,
            "alternatives": self.alternatives,
            "correct_index": self.correct_index,
            "media": _media_to_payload(self.media),
            "guess": (
                {"alternative": self.guess.alternative, "elapsed_ms": self.guess.elapsed_ms}
                if self.guess is not None
                else None
            ),
        }

    @classmethod
    def from_payload(
        cls, id: UUID, game_id: UUID, round_index: int, payload: dict[str, Any], score_delta: int | None
    ) -> "TriviumRound":
        round_ = cls(
            id=id,
            game_id=game_id,
            round_index=round_index,
            question_kind=payload["question_kind"],
            subject_id=UUID(payload["subject_id"]),
            params=payload["params"],
            alternatives=payload["alternatives"],
            correct_index=payload["correct_index"],
            media=_media_from_payload(payload["media"]),
        )
        guess_payload = payload["guess"]
        round_.guess = (
            Answer(alternative=guess_payload["alternative"], elapsed_ms=guess_payload["elapsed_ms"])
            if guess_payload is not None
            else None
        )
        round_.score_delta = score_delta
        return round_
