# Dateguessr

**Status:** ✓ Fully playable

## Inspiration

The same mechanic as Geoguessr, but swapping "where" for "when": instead of a map, a timeline is used.

## How to Play

Between 1 and 5 photos from the exact same day are shown, and the player must place them on a
timeline that looks like a measuring tape: large lines mark years, medium lines mark months, small
lines mark days. Scrolling zooms in or out so the exact point can be located precisely.

This repeats 5 times with photos from different dates each time, and scores from all 5 rounds are summed.

## Scoring & Game End

- When the player marks a date, the distance between the true date and their guess is measured.
- Guessing the exact date gives the maximum: 5000 points. Beyond that, the score decreases as the
  guessed date moves away from the true date (same decay logic as Geoguessr; exact equation not yet finalized).
- `has_next_round()`: a new round is created until round 5 is reached; on the 5th round, the game ends.

## Modes

| Mode | What to guess | Priority |
|---|---|---|
| `daysToDate` | Exact date (day) on the timeline | Implemented |
| `years` | Year only | Future (lowest priority) |
| `months` | Month only | Future (lowest priority) |

See [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) for when future modes are planned.
