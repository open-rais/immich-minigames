# Immichdle

**Status:** ✓ Fully playable

## Inspiration

Wordle-style games ([Wordle](https://www.nytimes.com/games/wordle/)), particularly the "guess the person"
variant (persondle): there's a hidden target and each attempt reveals comparative clues that narrow down the answer.

## Modes

| Mode | What to guess |
|---|---|
| `person` (persondle) | People - clues below |
| `album` (albumdle) | Albums - clues below |

Both modes share the same scoring/game-end rules (see below) and daily-challenge support; only the
target entity and its comparative clues differ.

## Persondle (`person`)

A random person is secretly chosen. The player tries names of other people as guesses. Each guess reveals
comparative clues about the mystery person:

The target isn't picked with uniform probability by default: an admin-configurable exponent `w` (0-1, default
0.2) biases the pick towards people with more photos, following `peso = c_fotos ^ w` - `w = 0` gives everyone
the same odds, `w = 1` makes a person with 1000 photos 1000x as likely to be picked as one with 1.

- **Age**: older, younger, same age, or unknown.
- **AssetCount**: more, fewer, or equal number of photos.
- **FirstAppearance**: whether this person's first asset is before, after, or the same as the mystery person's.
- **CommonNames**: splitting the name by spaces, how many first/last names they share with the mystery person.
- **MLSimilarity**: face similarity according to Immich-ML.
- **AssetsTogether**: how many photos include both the mystery person and this guess.

Every 5 guesses reveals an extra clue (in order): the number of names, the letter count of each name,
initials of each name, and finally their thumbnail.
**The initial version launches without the progressive clue reveal system**—all comparative clues above
are shown from the start; progressive reveals are a future feature (see roadmap item 16).

## Albumdle (`album`)

A random album is secretly chosen, biased towards albums with more assets by the same
admin-configurable exponent mechanism as persondle's (its own independent `asset_count_weight`
setting, not shared with persondle's). The player tries album names as guesses. Each guess reveals
comparative clues about the mystery album:

- **FirstAssetDate**: whether this album's earliest asset is before, after, or the same as the mystery
  album's.
- **AssetCount**: more, fewer, or equal number of assets.
- **CommonNames**: splitting the album name by spaces, how many words it shares with the mystery album's
  name (e.g. "Colbun 2022" and "Colbun 2023" share "colbun").
- **Similarity**: cosine similarity between the two albums' averaged CLIP embeddings (Immich's
  `smart_search` table - semantic/image embeddings, not face embeddings - averaged across each album's
  assets and cached, mirroring persondle's MLSimilarity caching approach; see
  [docs/ARCHITECTURE/IMMICH.md](../ARCHITECTURE/IMMICH.md)'s "Face similarity" section for the sibling
  cache this mirrors).
- **UniqueFaceCount**: more, fewer, or equal count of distinct *named* people appearing anywhere in the
  album's assets.
- **DominantFace**: the named person appearing in the most of the album's assets (ties broken by that
  person's total tagged-photo count across the whole library, then name). Shown as that person's
  thumbnail + name (plus "+N" when there was a tie). Colored guess-relative-to-target: green if the
  guessed album's dominant person (or any of a tied set) is also the mystery album's own dominant person;
  amber if they appear somewhere in the mystery album but aren't its dominant person; red if they don't
  appear in the mystery album at all; a plain "?" if the guessed album has no named person at all.

## Scoring & Game End

Both modes share the same rules:

- Starting score is 100 (admin-configurable per mode).
- Each wrong guess subtracts 5 points (admin-configurable per mode).
- Score never goes below 0: if a deduction would make it negative, it's floored at 0.
- `has_next_round()`: if the guess was correct, the game ends (won); if the score (floored at 0) reaches 0,
  the game ends (lost); otherwise, a new round is created.

## Daily

The target (person or album) is pre-picked once for the day (`PersondleGame.start(target=...)` /
`AlbumdleGame.start(target=...)`); guesses stay live otherwise - clue data (counts, ML/CLIP similarity)
is resolved at guess time same as a normal game, so two players guessing the same target on a busy
library day could see a marginally different clue if the library changed in between.
