# Trivium

**Status:** ✓ Fully playable (birthday, photos, location, mixed modes)

## Inspiration

Trivia/quiz shows like [Kahoot!](https://kahoot.com/) or [Trivia Crack](https://triviacrack.com/):
a multiple-choice question, four options, a countdown timer, and points that reward answering fast.
Here every question is built from your own Immich library instead of a generic trivia bank.

## How to Play

Each round shows a question with four alternatives. The question card and photo (if the question
has one) reveal first; once fully loaded, the question text fades in word by word, holds for a
moment, then the four alternatives slide up and a countdown timer starts.

- **Correct guess:** worth points based on how fast you answered (see Scoring below), and a new
  round begins.
- **Wrong guess, or running out of time:** the game ends immediately - unlike MoreOrLess/Timeline's
  tie handling, there's no partial credit here.
- **Infinite game:** a subject (the person or photo a question is about) won't repeat within the
  same game as long as the library has enough of them; once that pool runs out, repeats are allowed
  so a good run never ends early just because the library is small.

A mode isn't a single mechanic here - it's a **topic**. Each mode has several distinct question
types, and every round picks one at random from that mode's own set (the same type can come up
twice in a row). A question type that can't currently generate a valid round (e.g. fewer than 4
countries in the library) is simply skipped in favor of another one from the same mode, so a small
library never breaks a round.

## Scoring & Game End

Unlike every distance/time-decay game (Geoguessr, Dateguessr), scoring here is **linear** by answer
time, with two admin-configurable settings:

```
score = round(max_points * (1 - clamp(elapsed_ms, 0, answer_time_ms) / answer_time_ms))
```

With the defaults (100 points, 10 seconds), answering instantly scores 100, answering at the 5-second
mark scores 50, and answering at (or past) the limit scores 0. `has_next_round()`: a new round is
created only if the previous guess was correct - a wrong guess or a timeout ends the game.

## Modes

| Mode | Question types | Priority |
|---|---|---|
| `birthday` | What year was {person} born? / When is {person}'s birthday? / What day was {person} born? | Implemented |
| `photos` | Who has the most photos overall? / Who has the most photos with {person}? / What year is {person}'s first photo from? | Implemented |
| `location` | In what country/city was this photo taken? | Implemented |
| `mixed` | Every question type above, plus two exclusive to this mode: What's this person's name? (shown a face, pick the name) and Who is {person}? (shown a name, pick the face) | Implemented |

See [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) for when future modes are planned.

## Daily

The daily challenge's question sequence is pre-generated once for the day, up to an
admin-configured `chain_length` (default 100) - reaching the end ends the game as "perfect" instead
of a loss, same as every other chain-shaped daily mode. Because the alternatives for
numeric/date-based question types are generated with random noise, the daily spec freezes not just
each round's subject but which question type was picked *and* its exact four alternatives, so every
player of a given day sees byte-identical questions. Trivium's content is concrete people/assets, so
it also keeps the normal cross-day `no_repeat_days` window (like Timeline, unlike MoreOrLess).
