"""Pure unit tests (no DB) for Trivium's daily support
(games/trivium/daily.py::ScriptedQuestionType/exclusion_ids/game_kwargs). Hand-constructed
questions, so none of this needs the immich_service/db_session fixtures - see
tests/unit/services/test_daily_challenge_service.py's TestSpecShapePerGame/TestExclusionWindow for
the integration-level coverage (build_spec's actual shape, two players/days sharing or excluding
content) that does need those."""

from uuid import uuid4

from games.trivium.daily import ScriptedQuestionType, exclusion_ids, game_kwargs
from games.trivium.questions.base import GeneratedQuestion, MediaSpec


def _question(**overrides: object) -> GeneratedQuestion:
    defaults: dict[str, object] = {
        "question_kind": "birthday_year",
        "subject_id": uuid4(),
        "params": {"person_id": str(uuid4()), "person_name": "Someone"},
        "alternatives": [1990, 1991, 1992, 1993],
        "correct_index": 0,
        "media": MediaSpec(),
    }
    return GeneratedQuestion(**{**defaults, **overrides})  # type: ignore[arg-type]


class TestScriptedQuestionType:
    def test_generate_replays_questions_in_order(self):
        questions = [_question(question_kind="birthday_year"), _question(question_kind="photos_total_assets")]
        scripted = ScriptedQuestionType(questions, next_index=0)

        first = scripted.generate(immich_service=None, exclude_subject_ids=frozenset())
        second = scripted.generate(immich_service=None, exclude_subject_ids=frozenset())

        assert first is questions[0]
        assert second is questions[1]

    def test_ignores_exclude_subject_ids(self):
        # Same "already built repeat-free at generation time" convention as every other game's
        # scripted replay - a real subject exclusion set here must not filter anything out.
        question = _question()
        scripted = ScriptedQuestionType([question], next_index=0)

        result = scripted.generate(immich_service=None, exclude_subject_ids=frozenset({question.subject_id}))

        assert result is question

    def test_generate_returns_none_once_exhausted(self):
        scripted = ScriptedQuestionType([_question()], next_index=1)

        assert scripted.generate(immich_service=None, exclude_subject_ids=frozenset()) is None

    def test_resuming_mid_chain_continues_from_the_right_index(self):
        # Mirrors games/trivium/daily.py's game_kwargs after 2 rounds already exist:
        # next_index = rounds_played (2), no +1 offset (unlike MoreOrLess/Timeline's chain).
        questions = [_question(), _question(), _question(question_kind="location_country")]
        scripted = ScriptedQuestionType(questions, next_index=2)

        result = scripted.generate(immich_service=None, exclude_subject_ids=frozenset())

        assert result is questions[2]


class TestExclusionIds:
    def test_returns_every_subject_in_the_spec(self):
        questions = [_question(), _question(), _question()]
        spec = {
            "questions": [
                {
                    "question_kind": q.question_kind,
                    "subject_id": str(q.subject_id),
                    "params": q.params,
                    "alternatives": q.alternatives,
                    "correct_index": q.correct_index,
                    "media": {"kind": q.media.kind},
                }
                for q in questions
            ]
        }

        ids = exclusion_ids(spec)

        assert ids == {q.subject_id for q in questions}


class TestGameKwargs:
    def test_round_trips_a_question_through_the_payload_shape(self):
        original = _question(
            question_kind="mixed_name_to_face",
            alternatives=[{"person_id": str(uuid4()), "person_name": "A"}],
            media=MediaSpec(kind="person_thumbnail", person_id=uuid4()),
        )
        spec = {
            "questions": [
                {
                    "question_kind": original.question_kind,
                    "subject_id": str(original.subject_id),
                    "params": original.params,
                    "alternatives": original.alternatives,
                    "correct_index": original.correct_index,
                    "media": {"kind": original.media.kind, "person_id": str(original.media.person_id)},
                }
            ]
        }

        kwargs = game_kwargs(
            "mixed",
            spec,
            {},
            rounds_played=0,
            immich_service=None,
            ml_service=None,  # type: ignore[arg-type]
        )
        [question_type] = kwargs["question_types"]
        replayed = question_type.generate(immich_service=None, exclude_subject_ids=frozenset())

        assert replayed.question_kind == original.question_kind
        assert replayed.subject_id == original.subject_id
        assert replayed.alternatives == original.alternatives
        assert replayed.media.kind == "person_thumbnail"
        assert replayed.media.person_id == original.media.person_id
        assert kwargs["mode"] == "mixed"
