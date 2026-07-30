# Timeline

**Status:** ✓ Fully playable (arcade mode)

## Inspiration

The board game [Timeline](https://www.zygomatic-games.com/en/game/timeline-classic/): event cards are
inserted in the correct chronological order relative to cards already on the table.

## How to Play

Unlike Dateguessr (which places a photo at an absolute point on a timeline), here what matters is the
**relative** order of photos. The game starts with one photo already placed on the board, its date
visible. Round after round, a new photo is shown—its date hidden—and the player must pick a slot to
insert it into, relative to the photos already on the board.

- **Correct guess:** the card joins the board at its real chronological position, and another photo
  is drawn to place next.
- **Wrong guess:** the game ends. The final score is the streak of correctly placed cards.
- **Tied dates:** if a card's date exactly matches a neighbor already on the board, both slots next
  to it count as correct—nobody should lose over something indistinguishable.
- **Tolerance:** an admin-configurable `tolerance_days` (default 1) widens which slots count as
  correct, based on how far the guessed slot's neighbors are from the card's real date.
- **Spread:** when drawing the next card, the game prefers (best-effort, never blocks) one at least
  `min_separation_days` (default 30) from every date already on the board, so a run doesn't fill up
  with photos from the same trip.
- **Board cap:** by default the run is infinite (`max_cards = 0`). If an admin sets a cap, reaching
  it ends the run as a "perfect" one—no penalty, same as running out of eligible photos.

## Scoring & Game End

- Each correctly placed card is worth 1 point; the game's total score is the streak of correct
  placements, directly comparable on the leaderboard (same scoring shape as MoreOrLess).
- `has_next_round()`: if the guess was correct, wasn't blocked by an admin-configured `max_cards`
  cap, and there's still an eligible photo left in the library, a new round is created; otherwise the
  game ends. Running out of eligible photos or hitting `max_cards` both end the run as a win (a
  "perfect" streak), never as a loss.

## Modes

| Mode | What it does | Priority |
|---|---|---|
| `arcade` | Infinite run until a wrong guess (described above) | Implemented |
| `Level` | N photos given all at once, must all be ordered correctly | Future (see roadmap #21) |

See [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) for when future modes are planned.

## Daily

The daily challenge's card sequence is pre-generated once for the day, up to an admin-configured
`chain_length` (default 100)—reaching the end of the sequence ends the game as "perfect" instead of
a loss, same as the `max_cards` cap above. Unlike MoreOrLess (whose chain has no cross-day exclusion
at all), Timeline's cards are concrete assets, so it also keeps the normal `no_repeat_days` window
every other daily mode has—the first mode that needs both settings at once. See
[docs/TODO/DAILY-GAMES.md](../TODO/DAILY-GAMES.md).
