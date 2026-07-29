"""Pure candidate-spreading helper shared by any game that samples a random pool and wants to
avoid near-duplicate answers across rounds (Geoguessr/Dateguessr today) - see games/shared/'s
docstring for what belongs here and why."""

from collections.abc import Callable
from typing import TypeVar

_Candidate = TypeVar("_Candidate")
_Answer = TypeVar("_Answer")


def pick_spread_asset(
    candidates: list[_Candidate],
    previous_answers: list[_Answer],
    separation: Callable[[_Candidate, _Answer], float],
    min_separation: float,
) -> _Candidate | None:
    """Prefers the first candidate at least `min_separation` away (by `separation`) from every
    previous round's answer, so rounds don't test near-duplicate answers. Falls back to the first
    candidate if none qualifies, or None if there are no candidates at all."""
    if not candidates:
        return None
    for candidate in candidates:
        if all(separation(candidate, answer) >= min_separation for answer in previous_answers):
            return candidate
    return candidates[0]
