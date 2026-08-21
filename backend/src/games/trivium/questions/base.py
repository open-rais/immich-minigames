"""Contract for one Trivium question type - see docs/TODO/TRIVIUM.md §2.5 ("banco de tipos de
pregunta"). Each mode (games/trivium/modes.py) is a list of these; games/trivium/game.py's
TriviumGame never knows which concrete type generated a given round, only that every one produces
the same shape (games/trivium/round.py's TriviumRound)."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID

from services.immich import ContentQueries

MediaKind = Literal["none", "asset", "person_thumbnail", "person_thumbnails"]


@dataclass(frozen=True)
class MediaSpec:
    """What (if anything) a round needs rendered alongside its question - see TRIVIUM.md §2.5's
    "ninguna / un asset / un thumbnail de persona / cuatro thumbnails". Only "none" is ever
    produced by a type implemented so far (F1's birthday_year); the other kinds exist so a later
    phase (location's asset, mixed's face<->name types) doesn't need a payload shape change."""

    kind: MediaKind = "none"
    asset_id: UUID | None = None
    person_id: UUID | None = None
    person_ids: list[UUID] | None = None


NONE_MEDIA = MediaSpec()


@dataclass(frozen=True)
class GeneratedQuestion:
    """What a QuestionType hands back to TriviumGame to build a round from - see
    games/trivium/round.py's TriviumRound.of. `params`/`alternatives` are already JSON-safe (each
    question type owns turning any UUID/date into a plain str/int itself) - TRIVIUM.md §2.5's i18n
    note is that the frontend builds the actual phrase from `question_kind` + `params`, never a
    backend-assembled string, so nothing here is or contains one."""

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
    earlier in the same game (TriviumGame._used_subject_ids) - TRIVIUM.md §7's "que no salga la
    misma persona como sujeto dos veces en la misma partida"."""

    def can_generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> bool:
        """Whether this type has enough content to generate a round right now - False lets the
        mode fall back to a different type (TRIVIUM.md §2.5) instead of a broken round."""
        ...

    def generate(self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]) -> GeneratedQuestion:
        """Only ever called after can_generate() returned True for the same arguments."""
        ...
