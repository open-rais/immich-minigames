# Immichdle

**Status:** ✓ Fully playable

## Inspiration

Wordle-style games ([Wordle](https://www.nytimes.com/games/wordle/)), particularly the "guess the person"
variant (persondle): there's a hidden target and each attempt reveals comparative clues that narrow down the answer.

## How to Play

A random person is secretly chosen. The player tries names of other people as guesses. Each guess reveals
comparative clues about the mystery person:

- **Age**: older, younger, same age, or unknown.
- **AssetCount**: more, fewer, or equal number of photos.
- **FirstAppearance**: whether this person's first asset is before, after, or the same as the mystery person's.
- **CommonNames**: splitting the name by spaces, how many first/last names they share with the mystery person.
- **MLSimilarity**: face similarity according to Immich-ML.
- **AssetsTogether**: how many photos include both the mystery person and this guess.

Every 5 guesses reveals an extra clue (in order): the number of names, the letter count of each name,
initials of each name, and finally their thumbnail.
**The initial version launches without the progressive clue reveal system**—all comparative clues above
are shown from the start; progressive reveals are a future feature.

## Scoring & Game End

- Starting score is 100. This is correct **while the progressive clue system doesn't exist** (see Modes
  section—that's future work, roadmap item 11). When implemented, starting score should increase to ~200
  so the cost per wrong guess/revealed clue stays proportional without changing other rules. Until then,
  100 is the source of truth.
- Each wrong guess subtracts 5 points; each progressively revealed clue (future additions) subtracts 10 points.
- Score never goes below 0: if a deduction would make it negative, it's floored at 0.
- `has_next_round()`: if the guess was correct, the game ends (won); if the score (floored at 0) reaches 0,
  the game ends (lost); otherwise, a new round is created.

## Modes

| Mode | What to guess | Priority |
|---|---|---|
| `person` | People (comparative clues above) | Planned |
| `album` (albumdle) | Albums—clues: FirstAssetDate, AssetCount, ThumbMLSimilarity, CommonAssets, CommonNames, Duration (span between first and last asset) | Future |

See [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) for when modes are planned.
