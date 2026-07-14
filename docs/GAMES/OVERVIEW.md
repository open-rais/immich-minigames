# Games Overview

Immich Minigames transforms metadata already in your Immich instance (people, albums, dates, locations,
face similarity via Immich-ML) into memory/trivia minigames about your own photo library. Double benefit:
it's entertaining, and it rewards keeping your Immich metadata organized (names, birthdays, locations)
because that's what powers the games.

All games share the same technical foundation (see below) and differ only in two ways: which Immich
metadata they use as the question, and how they calculate the score. This means adding a new game is
theoretically just adding those two rules—everything else (persistence, round loop, generic API) is
already handled by the shared base.

## Shared Foundation: `Game` and `Round`

Each played game is a **`Game`**: it has an id, an owner (who's playing), an accumulated score, a list
of `Round`s played so far, and a flag for whether it's finished (`finished`).

Each individual question within a game is a **`Round`**: it has an id, a reference to its `Game`, an
index (which round number), the correct answer to compare against the player's guess, the actual guess
the player entered, and the entities shown (assets and/or people depending on the game)—the latter two
are saved so the round can be reconstructed later (for the future "View rounds" feature and the future
ability to report incorrect metadata).

The game loop is always the same, regardless of which minigame it is:

1. The player is shown the current round's question (defined by the correct answer the `Round` stores).
2. The player sends their guess.
3. The `Round` calculates the score delta for that play (`calculate_score()`)—can be positive or negative,
   and this rule is specific to each game (see each game's doc).
4. The `Game` applies that delta to its accumulated score.
5. The `Game` decides whether to create a new round (`has_next_round()`)—this rule is also game-specific
   (e.g., "until round 5", "until one wrong guess", "until you guess correctly or run out of points").
   If a new round is created, it knows about previous rounds to avoid repeating candidates within the
   same game. If not, the `Game` is marked `finished`.
6. If there's no new round, the `Game` is `finished`.

Thanks to this design (Template Method pattern), each new game only needs to answer two questions—
"when does this game end?" and "how many points is this guess worth?"—everything else (API, persistence,
orchestration) is shared.

## Game Catalog

| Game | Inspiration | Core mechanic | Status | Doc |
|---|---|---|---|---|
| MoreOrLess | Classic [More Or Less](https://moreorless.io/) | Compare if candidate B has more/fewer of a stat than A; wrong guess ends game | ✓ Playable | [MORE_OR_LESS.md](./MORE_OR_LESS.md) |
| Geoguessr | [GeoGuessr](https://www.geoguessr.com/) | Mark location on map where photo was taken; score decays with distance | ✓ Playable | [GEOGUESSR.md](./GEOGUESSR.md) |
| Dateguessr | Geoguessr, but with dates | Mark date on timeline when photo was taken; score decays with time difference | ✓ Playable | [DATEGUESSR.md](./DATEGUESSR.md) |
| Immichdle | Wordle-style games ([Wordle](https://www.nytimes.com/games/wordle/)) | Guess mystery person from comparative clues; fewer points per wrong guess | ✗ Design stub | [IMMICHDLE.md](./IMMICHDLE.md) |
| Timeline | Board game [Timeline](https://www.zygomatic-games.com/en/game/timeline-classic/) | Insert photos in correct chronological order relative to already-placed ones | ✗ Design stub | [TIMELINE.md](./TIMELINE.md) |
| Who'sThatPerson | ["Who's That Pokémon?"](https://pokemon.fandom.com/wiki/Who's_That_Pok%C3%A9mon%3F) | Guess person's name when their face is hidden in a photo | ✗ Design stub | [WHOS_THAT_PERSON.md](./WHOS_THAT_PERSON.md) |

Each game also has additional "modes" (variants of which data is used as the question) that are lower
priority and will come later. See [`docs/TODO/ROADMAP.md`](../TODO/ROADMAP.md) for the actual implementation
order. Details about each mode are in its game's doc.
