"""Trivium's DailySupport implementation (games/daily.py's contract): generates a day's shared
content, decides which ids future days must avoid repeating, and builds the kwargs to replay it
against the *same* TriviumGame class a normal game uses.

Freezes more than most games' daily spec (see games/trivium/game.py's own module docstring for the
game's general shape): not just each round's subject, but which question type generated it and its
exact 4 alternatives. The distractors are randomized (games/trivium/questions/_shared.py's noise,
photos_together's random-4-of-N sampling, ...), so two players of the same day's challenge must see
byte-identical alternatives, not just the same subject, or the leaderboard stops being comparable."""

from typing import Any
from uuid import UUID, uuid4

from games.trivium.game import TriviumGame
from games.trivium.modes import MODES
from games.trivium.pooled_content import PooledContentQueries
from games.trivium.questions.base import GeneratedQuestion
from games.trivium.round import TriviumRound, media_from_payload, media_to_payload
from services.immich import ContentQueries, ImmichService
from services.ml_service import MLService


class ScriptedQuestionType:
    """Replays a pre-generated sequence of questions instead of drawing from a mode's real question
    bank (games/trivium/modes.py's pick_question, which shuffles and tries each type in turn) - the
    daily counterpart to e.g. games/timeline/daily.py's ScriptedContent. Ignores
    exclude_subject_ids entirely, same "already built repeat-free at generation time" reasoning as
    every other game's scripted replay - re-applying it here would be redundant. A game's
    `question_types` is normally a whole mode's bank (several types); a scripted daily game instead
    gets a list of exactly one of these, so games/trivium/modes.py's pick_question trivially always
    picks it."""

    def __init__(self, questions: list[GeneratedQuestion], next_index: int) -> None:
        self._questions = questions
        self._next_index = next_index

    def generate(
        self, immich_service: ContentQueries, exclude_subject_ids: frozenset[UUID]
    ) -> GeneratedQuestion | None:
        if self._next_index >= len(self._questions):
            return None
        question = self._questions[self._next_index]
        self._next_index += 1
        return question


def _round_to_question_dict(round_: TriviumRound) -> dict[str, Any]:
    return {
        "question_kind": round_.question_kind,
        "subject_id": str(round_.subject_id),
        "params": round_.params,
        "alternatives": round_.alternatives,
        "correct_index": round_.correct_index,
        "media": media_to_payload(round_.media),
    }


def _question_from_dict(payload: dict[str, Any]) -> GeneratedQuestion:
    return GeneratedQuestion(
        question_kind=payload["question_kind"],
        subject_id=UUID(payload["subject_id"]),
        params=payload["params"],
        alternatives=payload["alternatives"],
        correct_index=payload["correct_index"],
        media=media_from_payload(payload["media"]),
    )


def build_spec(mode: str, immich_service: ContentQueries, settings: dict[str, float]) -> dict[str, Any]:
    # TriviumGame.has_next_round() checks the *previous* round's `correct` (a real guess) -
    # meaningless for a precomputed chain, so this drives create_next_round() directly for a fixed
    # length instead, the same shape as games/timeline/daily.py's own build_spec. Unlike MoreOrLess/
    # Timeline's chain (where round 1 draws 2 raw entries to seed a comparison), every Trivium round
    # is a fully self-contained question, so there's no "len(chain) < chain_length + 1" offset here
    # - round count and question count are 1:1.
    chain_length = int(settings.get("chain_length", 100))
    question_types = MODES[mode]
    # Pools/memoizes the handful of query shapes every question type re-issues from scratch on
    # each generate() call - see PooledContentQueries' own docstring. Scoped to this build_spec
    # call only; live games keep using immich_service straight (services/game_factory.py).
    pooled_content = PooledContentQueries(immich_service)
    game = TriviumGame.start(
        id=uuid4(), mode=mode, immich_service=pooled_content, question_types=question_types, settings=settings
    )
    while len(game.rounds) < chain_length:
        game.rounds.append(game.create_next_round())
    return {"questions": [_round_to_question_dict(r) for r in game.rounds]}


def exclusion_ids(spec: dict[str, Any]) -> set[UUID]:
    # Every question's subject is answer-content (no decorative extras) - all of it must stay out
    # of a future day's chain. Mixing person ids (birthday/photos/mixed) and asset ids (location) in
    # one set is harmless - they're different tables, exclude_ids is just a generic frozenset[UUID].
    return {UUID(q["subject_id"]) for q in spec["questions"]}


def game_kwargs(
    mode: str,
    spec: dict[str, Any],
    settings: dict[str, float],
    *,
    rounds_played: int,
    immich_service: ImmichService,
    ml_service: MLService,
) -> dict[str, Any]:
    questions = [_question_from_dict(q) for q in spec["questions"]]
    # rounds_played, not rounds_played + 1 - unlike MoreOrLess/Timeline's chain offset (see
    # build_spec above), round N always consumes exactly questions[N - 1], so "how many are already
    # played" is directly "the index of the next fresh one".
    return {
        "mode": mode,
        "immich_service": immich_service,
        "question_types": [ScriptedQuestionType(questions, rounds_played)],
        "settings": settings,
    }
