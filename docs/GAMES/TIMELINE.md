# Timeline

**Status:** ✗ Design stub (not yet implemented)

## Inspiration

The board game [Timeline](https://www.zygomatic-games.com/en/game/timeline-classic/): event cards are
inserted in the correct chronological order relative to cards already on the table.

## How to Play

Unlike Dateguessr (which places a photo at an absolute point on a timeline), here what matters is the
**relative** order of photos. A starting photo is given already placed, then another photo is given and
the player must insert it in the correct position relative to photos already on the timeline.

- **arcade** (initial mode): start with one photo, get another; if placed correctly, get another (and
  so on); if wrong, the game ends.
- **Level** (future mode): N photos are given all at once and must all be ordered correctly.

## Scoring & Game End

To be defined precisely—the `TimelineGame`/`TimelineRound` docstring in `games/timeline.py` is not yet
written. What's clear about arcade mode: correct placement continues the streak, wrong placement ends
the game (same pattern as MoreOrLess). The exact scoring formula (fixed points per correct placement?
varies with how many photos are already placed?) will be decided before implementation.

## Modes

| Mode | Priority |
|---|---|
| `arcade` | Planned |
| `Level` | Future (see roadmap) |

See [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) for when modes are planned.
