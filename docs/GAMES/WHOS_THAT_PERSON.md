# Who'sThatPerson

**Status:** ✓ Fully playable

## Inspiration

The ["Who's That Pokémon?"](https://pokemon.fandom.com/wiki/Who's_That_Pok%C3%A9mon%3F) segment from
the Pokémon anime: a silhouette is shown and you must guess who it is before it's revealed.

## How to Play

A photo with one or more people is shown. The rectangles where faces appear (detected by Immich's face
recognition) are covered with a black box. The player clicks on one of those boxes and types the name
of the person they think is there.

- Maximum 5 hidden faces per photo.
- New photos are shown until **15 people total are asked about** (15 rounds), regardless of whether
  the guess was correct—a game can end with anywhere from 0/15 to 15/15 correct guesses.

## Scoring & Game End

- `has_next_round()`: a new round is created while questions remain under the 15th person
  (`round_index < 15`); on the 15th round, the game ends.
- `calculate_score()`: combo-style accumulated scoring—each correct guess adds the current streak value
  (which grows by 1 for each consecutive correct guess, starting at 1); a wrong guess resets the streak
  to 0 and adds no points that round (but doesn't subtract previously earned points). Example with 6 rounds
  (correct-correct-correct-wrong-correct-correct): +1, +2, +3, +0, +1, +2 → final score 9.
