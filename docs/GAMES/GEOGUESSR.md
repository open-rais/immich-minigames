# Geoguessr

**Status:** ✓ Fully playable

## Inspiration

The online game [GeoGuessr](https://www.geoguessr.com/): given a photo, guess where on a map it was taken.

## How to Play

Between 1 and 5 photos that share a location (with minor distance variations between them) are shown.
The player marks on a map where they think the photos were taken.

This repeats 5 times with different locations each time, and scores from all 5 rounds are summed.

## Scoring & Game End

- When the player marks a location, the distance between the true location and their guess is measured.
- Guessing within 1 km gives the maximum: 5000 points. Beyond that, the score decreases as the guessed
  distance moves away from the true location (decay formula; exact equation not yet finalized).
- `has_next_round()`: a new round is created until round 5 is reached; on the 5th round, the game ends.

## Modes

| Mode | What to guess | Priority |
|---|---|---|
| `distanceBetweenGuess` | Exact point on the map (score by distance) | Implemented |
| `country` | Country only | Future (lowest priority) |
| `city` | City only | Future (lowest priority) |

See [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) for when future modes are planned.
