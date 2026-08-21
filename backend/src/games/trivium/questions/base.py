"""Contract for one Trivium question type - the "bank" of question types a mode draws from. Each
mode (games/trivium/modes.py) is a list of these; games/trivium/game.py's TriviumGame never knows
which concrete type generated a given round, only that every one produces the same shape
(games/trivium/round.py's TriviumRound)."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID

from services.immich import ContentQueries

MediaKind = Literal["none", "asset", "person_thumbnail", "person_thumbnails"]


@dataclass(frozen=True)
class MediaSpec:
    """What (if anything) a round needs rendered alongside its question - none, a single asset, a
    single person thumbnail, or several person thumbnails. Only "none" is ever produced by the
    question type implemented so far (birthday_year); the other kinds exist so a future question
    type (an asset-based one, a face<->name one) doesn't need a payload shape change."""

    kind: MediaKind = "none"
    asset_id: UUID | None = None
    person_id: UUID | None = None
    person_ids: list[UUID] | None = None


NONE_MEDIA = MediaSpec()


@dataclass(frozen=True)
class GeneratedQuestion:
    """What a QuestionType hands back to TriviumGame to build a round from - see
    games/trivium/round.py's TriviumRound.of. `params`/`alternatives` are already JSON-safe (each
    question type owns turning any UUID/date into a plain str/int itself). The frontend builds the
    actual phrase from `question_kind` + `params` (the app is translated ES/EN) - nothing here is
    or contains a pre-built sentence."""

    question_kind: str
    subject_id: UUID
    params: dict[str, Any]
    alternatives: list[Any]
    correct_index: int
    media: MediaSpec = NONE_MEDIA


class QuestionType(Protocol):
    """One question type within a mode (games/trivium/modes.py) - e.g. "what year was {person}
    born". Picks its own subject, builds its own correct answer plus 3 distractors, and declares
    what media (if any) the round needs. `exclude_subject_ids` is every subject already used
    earlier in the same game (TriviumGame._used_subject_ids) - a subject never repeats within one
    game."""

    def can_generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> bool:
        """Whether this type has enough content to generate a round right now - False lets the
        mode fall back to a different type instead of a broken round."""
        ...

    def generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> GeneratedQuestion:
        """Only ever called after can_generate() returned True for the same arguments."""
        ...
