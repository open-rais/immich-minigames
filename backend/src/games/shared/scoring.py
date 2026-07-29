"""Pure scoring curve shared by any game that wants exponential-decay-by-distance scoring
(Geoguessr/Dateguessr today) - see games/shared/'s docstring for what belongs here and why."""

import math


def exp_decay_score(distance: float, flat_zone: float, decay: float, max_score: int) -> int:
    """`max_score` within a flat zone around the exact answer, then
    `round(max_score * exp(-distance / decay))` beyond it, floored at 0. `distance` and its units
    are game-specific (km for Geoguessr, days for Dateguessr). `max_score` has no default - it's a
    design constant owned by whichever game calls this, never by this shared module (see
    docs/TODO/DECOUPLING.md §4, Fase 1)."""
    if distance <= flat_zone:
        return max_score
    return max(0, round(max_score * math.exp(-distance / decay)))
