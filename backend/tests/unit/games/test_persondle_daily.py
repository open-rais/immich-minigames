"""Pure unit test (no DB) for Persondle's daily support. Persondle needs no content seam of its
own (games/immichdle/daily.py's docstring explains why) - PersondleGame.start() already accepts a
pre-picked `target`, which this covers directly."""

from datetime import date
from uuid import uuid4

import pytest

from domain.person import Person
from games.immichdle import PersondleGame, PersonSnapshot
from games.immichdle.persondle import build_spec


class TestPersondleGameWithTarget:
    def test_uses_the_given_target_without_sampling(self):
        target = PersonSnapshot(
            id=uuid4(), name="Target Person", asset_count=10, birth_date=None, first_asset_date=None
        )

        game = PersondleGame.start(id=uuid4(), immich_service=None, target=target)  # type: ignore[arg-type]

        assert game.target == target
        assert len(game.rounds) == 1


def _fake_person(*, birth_date: date | None = None) -> Person:
    return Person(id=uuid4(), name="Someone", birth_date=birth_date, asset_count=1)


class _FakeImmichService:
    """Minimal ContentQueries stand-in - build_spec() only needs get_persons/
    get_person_first_asset_date, not the DB-backed fixture the rest of this game's tests use."""

    def __init__(self, get_persons_impl) -> None:
        self._get_persons_impl = get_persons_impl
        self.calls: list[dict] = []

    def get_persons(self, **kwargs):
        self.calls.append(kwargs)
        return self._get_persons_impl(kwargs)

    def get_person_first_asset_date(self, person_id):
        return None


class TestBuildSpecRequireBirthDate:
    def test_filters_only_the_target_selection_call(self):
        target_with_birthdate = _fake_person(birth_date=date(1990, 1, 1))

        def get_persons_impl(kwargs):
            if kwargs.get("with_birthdate"):
                return [target_with_birthdate]
            return [_fake_person(), _fake_person()]

        service = _FakeImmichService(get_persons_impl)

        spec = build_spec(service, {"require_birth_date": 1})

        assert spec["target"]["id"] == str(target_with_birthdate.id)
        assert service.calls[0]["with_birthdate"] is True
        assert service.calls[1].get("with_birthdate") is None

    def test_off_by_default_does_not_filter(self):
        service = _FakeImmichService(lambda kwargs: [_fake_person(), _fake_person()][: kwargs["limit"]])

        build_spec(service, {})

        assert service.calls[0]["with_birthdate"] is None

    def test_no_person_with_a_birth_date_raises_a_specific_error(self):
        service = _FakeImmichService(lambda kwargs: [])

        with pytest.raises(ValueError, match="require_birth_date is enabled"):
            build_spec(service, {"require_birth_date": 1})
