# MoreOrLess

**Status:** ✓ Fully playable

## Inspiration

The classic [More Or Less](https://moreorless.io/): compare whether an unknown value is greater or
lesser than a known one. It's the same mechanic behind "guess the price" segments on TV game shows.

## How to Play

Person A is shown along with their real count (e.g., "Person A has 107 photos"). Then person B is shown
without their count. The player must guess whether B has **more** or **fewer** than A.

- **Correct guess:** B becomes the new reference (with their count now visible), a random candidate C
  is chosen, and the question repeats.
- **Wrong guess:** the game ends.
- **Tie** (A and B have exactly the same count): regardless of what the player answered, it's treated
  as a correct guess and doesn't end the game. Ties are avoided when possible when picking candidates
  (see `_pick_non_tied_candidate` in `more_or_less.py`), but if one does occur (e.g., many people with
  the same asset count), it shouldn't unfairly end the game.
- **Infinite game:** candidates can repeat. There's no fixed pool of people, so the game can't rely on
  "never repeat." What's avoided is repeating someone shown very recently—the last `_RECENT_EXCLUDE_WINDOW`
  people (10 at the time of writing) are tracked and won't be picked again until they "fall off the radar"
  (exit that window).

## Scoring & Game End

- Each correct (or tied) round is worth 1 point; the game's total score is the count of consecutive
  correct guesses (the streak).
- `has_next_round()`: if the guess was correct (or tied), a new round is created; if it was wrong,
  the game ends. The game doesn't end by running out of new candidates—see "infinite game" note above.

## Modes

| Mode | What's compared | Priority |
|---|---|---|
| `personAssets` | Photo/video count for a person | Implemented |
| `albumAssets` | Photo/video count for an album | Implemented |
| `assetDate` | Date a photo was taken | Future |
| `personBirthDate` | Person's birthday | Future |

See [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) for when future modes are planned.
