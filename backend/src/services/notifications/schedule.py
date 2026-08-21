"""Pure decision functions for the notification scheduler - given `now` and already-fetched data,
what (if anything) should be sent. No I/O, no session, no clock reads: runner.py is the only place
that calls datetime.now()/opens a session, so every rule here is testable with plain literal
values, no freezegun or thread involved (this codebase's own convention for "as of a date" logic -
see e.g. DailyGamesService.get_daily_status's `today` parameter).
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal

from games.registry import GAMES

# The four fixed times of day (server-local, "hora del servidor" - a single TZ per installation,
# not per user). Not admin-configurable yet - see the design doc's open questions.
SLOT_TIMES: dict[str, time] = {
    "daily_available": time(10, 0),
    "birthdays": time(12, 0),
    "album_anniversary": time(14, 0),
    "daily_reminder": time(21, 0),
}

# If the backend was down at the slot's exact time, it still sends within this window after
# restarting - past it, sending would be misleading ("daily's ready" at 23:00 is late enough it
# reads as wrong) rather than merely late.
GRACE_MINUTES = 60

# Deterministic tie-break for a streak tied across multiple modes - games/registry.py's own
# declaration order, not random, so the same tick re-run (e.g. a restart within the grace window)
# always picks the same mode.
_MODE_ORDER: dict[tuple[str, str], int] = {key: i for i, key in enumerate(GAMES)}


def active_kinds_for_tick(now: datetime) -> list[str]:
    """Which of the four kinds are inside their grace window right now - almost always zero or
    one (the slots are hours apart, the window is 60 minutes), but nothing here assumes that."""
    active = []
    for kind, slot_time in SLOT_TIMES.items():
        slot_start = datetime.combine(now.date(), slot_time)
        if slot_start <= now < slot_start + timedelta(minutes=GRACE_MINUTES):
            active.append(kind)
    return active


@dataclass(frozen=True)
class DailyNotification:
    kind: Literal["daily_available", "daily_reminder"]
    variant: Literal["streak_at_risk", "generic"] | None = None
    game_type: str | None = None
    mode: str | None = None
    streak: int | None = None


def decide_daily_notification(
    enabled_modes: list[tuple[str, str]],
    unfinished_modes: list[tuple[str, str]],
    streaks: dict[tuple[str, str], int],
) -> DailyNotification | None:
    """The full daily-reminder rule table for one user. `streaks` is racha(m) counted through
    **yesterday** (as_of = today - 1), never through today - through-today is the leaderboard badge's own
    question (persistence/games_repository.py's daily_streaks), and reusing it as-is here would
    make every mode not yet played today read as streak 0 and collapse this entire table (a mode
    played every day including today would show the same racha as one whose streak just started
    today - the two must NOT look identical to a 21:00 "you're about to lose it" check, since the
    first one both isn't at risk today (already played) and would still show as == 0 if counted
    through yesterday only when they've genuinely never played it before).

    `enabled_modes` is H, `unfinished_modes` is U (⊆ H, from get_daily_status's non-"finished"
    entries) - the caller resolves both live, this function makes no Immich/DB call of its own.

    Mutually exclusive result: a user with any active streak (`racha(m) > 0` for some m in H)
    never gets "daily_available" back, and a user with none never gets "daily_reminder" - so a
    caller processing the 10:00 tick only acts on results with kind == "daily_available", and the
    21:00 tick only on kind == "daily_reminder"; either kind at the other's tick is a caller bug,
    not a case this function itself needs to gate."""
    if not enabled_modes:
        return None

    max_streak = max((streaks.get(m, 0) for m in enabled_modes), default=0)
    if max_streak == 0:
        return DailyNotification(kind="daily_available")

    if not unfinished_modes:
        return None

    at_risk = [m for m in unfinished_modes if streaks.get(m, 0) > 0]
    if not at_risk:
        return DailyNotification(kind="daily_reminder", variant="generic")

    best = max(at_risk, key=lambda m: (streaks.get(m, 0), -_MODE_ORDER.get(m, 0)))
    return DailyNotification(
        kind="daily_reminder", variant="streak_at_risk", game_type=best[0], mode=best[1], streak=streaks[best]
    )
