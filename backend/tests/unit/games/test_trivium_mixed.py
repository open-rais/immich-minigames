"""Trivium's `mixed` mode's two exclusive question types (face -> name, name -> face). Happy-path
generation is tested against the real dev Immich Postgres (see tests/conftest.py) - the "library
doesn't give enough" edge cases (fewer than 4 named people, a same-name collision) use a small
in-memory ContentQueries double instead."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from domain.person import Person
from games.trivium.questions.base import GeneratedQuestion
from games.trivium.questions.mixed_face_to_name import KIND as FACE_TO_NAME_KIND
from games.trivium.questions.mixed_face_to_name import MixedFaceToNameQuestion
from games.trivium.questions.mixed_name_to_face import KIND as NAME_TO_FACE_KIND
from games.trivium.questions.mixed_name_to_face import MixedNameToFaceQuestion


def _person(name: str) -> Person:
    return Person(id=uuid4(), name=name, birth_date=None, asset_count=0)


@dataclass
class _FakeImmich:
    persons: list[Person] = field(default_factory=list)

    def get_persons(
        self,
        *,
        named_only: bool = True,
        randomize: bool = False,
        limit: int = 1,
        exclude_ids: frozenset[UUID] = frozenset(),
        **kwargs,
    ) -> list[Person]:
        pool = [p for p in self.persons if p.id not in exclude_ids]
        return pool[:limit]


class TestMixedFaceToNameQuestionAgainstRealData:
    def test_can_generate_is_true_with_the_dev_library(self, immich_service):
        assert MixedFaceToNameQuestion().can_generate(immich_service, frozenset())

    def test_generate_returns_a_well_formed_question(self, immich_service):
        question = MixedFaceToNameQuestion().generate(immich_service, frozenset())

        assert isinstance(question, GeneratedQuestion)
        assert question.question_kind == FACE_TO_NAME_KIND
        assert len(question.alternatives) == 4
        assert len(set(question.alternatives)) == 4  # names guaranteed distinct
        assert 0 <= question.correct_index < 4
        assert question.media.kind == "person_thumbnail"
        assert question.media.person_id == question.subject_id


class TestMixedFaceToNameQuestionEdgeCases:
    def test_can_generate_is_false_with_fewer_than_four_people(self):
        immich = _FakeImmich(persons=[_person("A"), _person("B"), _person("C")])
        assert MixedFaceToNameQuestion().can_generate(immich, frozenset()) is False

    def test_can_generate_is_false_when_every_eligible_subject_is_excluded(self):
        people = [_person(f"P{i}") for i in range(4)]
        immich = _FakeImmich(persons=people)
        assert MixedFaceToNameQuestion().can_generate(immich, frozenset(p.id for p in people)) is False

    def test_same_name_people_never_produce_ambiguous_alternatives(self):
        # Two people sharing a name - any group including both would make that name ambiguous as a
        # bare string, so a valid group must avoid picking both at once.
        twin_a, twin_b = _person("Same Name"), _person("Same Name")
        others = [_person(f"P{i}") for i in range(4)]
        immich = _FakeImmich(persons=[twin_a, twin_b, *others])

        for _ in range(20):
            question = MixedFaceToNameQuestion().generate(immich, frozenset())
            assert len(set(question.alternatives)) == 4


class TestMixedNameToFaceQuestionAgainstRealData:
    def test_can_generate_is_true_with_the_dev_library(self, immich_service):
        assert MixedNameToFaceQuestion().can_generate(immich_service, frozenset())

    def test_generate_returns_a_well_formed_question(self, immich_service):
        question = MixedNameToFaceQuestion().generate(immich_service, frozenset())

        assert isinstance(question, GeneratedQuestion)
        assert question.question_kind == NAME_TO_FACE_KIND
        assert len(question.alternatives) == 4
        assert len({alt["person_id"] for alt in question.alternatives}) == 4
        assert str(question.subject_id) in {alt["person_id"] for alt in question.alternatives}
        assert question.params["person_id"] == str(question.subject_id)
        assert question.media.kind == "none"


class TestMixedNameToFaceQuestionEdgeCases:
    def test_can_generate_is_false_with_fewer_than_four_people(self):
        immich = _FakeImmich(persons=[_person("A"), _person("B"), _person("C")])
        assert MixedNameToFaceQuestion().can_generate(immich, frozenset()) is False

    def test_can_generate_is_false_when_no_subject_is_eligible(self):
        people = [_person(f"P{i}") for i in range(4)]
        immich = _FakeImmich(persons=people)
        assert MixedNameToFaceQuestion().can_generate(immich, frozenset(p.id for p in people)) is False
