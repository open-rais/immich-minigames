"""DailyChallengeService.get_or_create_challenge. Integration tests against the real
dev Immich DB (see conftest.py's module docstring) - every (challenge_date, game_type, mode) used
here must be unique across this whole test session, hence the ever-increasing _next_date() below
(mirrors test_daily_games_service.py's own date counter, anchored to a different base date so the
two files' ranges can never collide)."""

import itertools
import threading
import uuid
from datetime import date, timedelta

import pytest

from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr import MODE_DAYS_TO_DATE
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS
from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle import MODE_PERSON
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import MODE_ALBUM_ASSETS, MODE_PERSON_ASSETS, MODE_PERSON_BIRTH_DATE
from games.timeline import GAME_TYPE as TIMELINE_TYPE
from games.timeline import MODE_ARCADE as TIMELINE_MODE_ARCADE
from games.whos_that_person import GAME_TYPE as WHOS_THAT_PERSON_TYPE
from games.whos_that_person import MODE_NAMED_FACES
from persistence.base import get_session_factory
from persistence.daily import DailyConfigModel
from persistence.users import UserModel
from services.daily_challenge_service import DailyChallengeService

_date_counter = itertools.count()
_BASE_DATE = date(2020, 1, 1)

_TOUCHED_GAME_TYPES = [
    MORE_OR_LESS_TYPE,
    GEOGUESSR_TYPE,
    DATEGUESSR_TYPE,
    IMMICHDLE_TYPE,
    WHOS_THAT_PERSON_TYPE,
    TIMELINE_TYPE,
]


def _next_date() -> date:
    # A big step (not +1 day) between calls - several tests below derive a "next day"/"N days
    # later" date from one _next_date() call via a manual +timedelta (e.g. TestExclusionWindow),
    # which would otherwise land on - and collide with - a *different* test's own _next_date()
    # base and its pre-existing DailyChallengeModel row for the same (game_type, mode).
    return _BASE_DATE + timedelta(days=next(_date_counter) * 1000)


@pytest.fixture(autouse=True)
def _clean_daily_configs(db_session):
    # Same rationale as test_daily_settings_service.py's cleanup fixture - daily_configs rows are
    # keyed by a fixed (game_type, mode), shared across every test (and test file) in this
    # session. This file's tests set daily-only overrides (chain_length/total_rounds/
    # total_people/no_repeat_days) on every game_type, so it cleans all five rather than just one.
    def _clear():
        db_session.query(DailyConfigModel).filter(DailyConfigModel.game_type.in_(_TOUCHED_GAME_TYPES)).delete(
            synchronize_session=False
        )
        db_session.commit()

    _clear()
    yield
    _clear()


class TestSpecShapePerGame:
    def test_more_or_less_person_assets_chain_length(self, daily_challenge_service, daily_settings_service):
        daily_settings_service.update_settings(MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS, values={"chain_length": 10})

        challenge = daily_challenge_service.get_or_create_challenge(_next_date(), MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS)

        assert len(challenge.spec["chain"]) == 11  # chain_length + 1
        assert "id" in challenge.spec["chain"][0]

    def test_more_or_less_album_assets_chain_length(self, daily_challenge_service, daily_settings_service):
        daily_settings_service.update_settings(MORE_OR_LESS_TYPE, MODE_ALBUM_ASSETS, values={"chain_length": 10})

        challenge = daily_challenge_service.get_or_create_challenge(_next_date(), MORE_OR_LESS_TYPE, MODE_ALBUM_ASSETS)

        assert len(challenge.spec["chain"]) == 11

    def test_more_or_less_person_birth_date_chain_length(self, daily_challenge_service, daily_settings_service):
        daily_settings_service.update_settings(
            MORE_OR_LESS_TYPE, MODE_PERSON_BIRTH_DATE, values={"chain_length": 10}
        )

        challenge = daily_challenge_service.get_or_create_challenge(
            _next_date(), MORE_OR_LESS_TYPE, MODE_PERSON_BIRTH_DATE
        )

        assert len(challenge.spec["chain"]) == 11
        assert isinstance(challenge.spec["chain"][0]["value"], str)  # ISO date, not an asset-count int

    def test_geoguessr_rounds(self, daily_challenge_service, daily_settings_service):
        daily_settings_service.update_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, values={"total_rounds": 2})

        challenge = daily_challenge_service.get_or_create_challenge(
            _next_date(), GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS
        )

        assert len(challenge.spec["rounds"]) == 2
        assert "id" in challenge.spec["rounds"][0]["main"]
        assert "extras" in challenge.spec["rounds"][0]

    def test_dateguessr_rounds(self, daily_challenge_service, daily_settings_service):
        daily_settings_service.update_settings(DATEGUESSR_TYPE, MODE_DAYS_TO_DATE, values={"total_rounds": 2})

        challenge = daily_challenge_service.get_or_create_challenge(_next_date(), DATEGUESSR_TYPE, MODE_DAYS_TO_DATE)

        assert len(challenge.spec["rounds"]) == 2
        assert "date" in challenge.spec["rounds"][0]["main"]

    def test_immichdle_target(self, daily_challenge_service):
        challenge = daily_challenge_service.get_or_create_challenge(_next_date(), IMMICHDLE_TYPE, MODE_PERSON)

        assert "id" in challenge.spec["target"]
        assert "name" in challenge.spec["target"]

    def test_whos_that_person_rounds_cover_the_configured_total(self, daily_challenge_service, daily_settings_service):
        daily_settings_service.update_settings(
            WHOS_THAT_PERSON_TYPE, MODE_NAMED_FACES, values={"total_people": 2, "max_hidden_faces": 2}
        )

        challenge = daily_challenge_service.get_or_create_challenge(
            _next_date(), WHOS_THAT_PERSON_TYPE, MODE_NAMED_FACES
        )

        assert sum(len(r["faces"]) for r in challenge.spec["rounds"]) >= 2
        assert "asset_id" in challenge.spec["rounds"][0]

    def test_effective_settings_are_snapshotted_onto_the_challenge(
        self, daily_challenge_service, daily_settings_service
    ):
        daily_settings_service.update_settings(GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS, values={"total_rounds": 2})

        challenge = daily_challenge_service.get_or_create_challenge(
            _next_date(), GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS
        )

        assert challenge.settings["total_rounds"] == 2
        assert challenge.settings["decay_km"] == 1500.0  # untouched key still falls back to its default

    def test_timeline_cards_chain_length(self, daily_challenge_service, daily_settings_service):
        # The first mode with both chain_length *and* no_repeat_days (see TestExclusionWindow's own
        # timeline test below for that half).
        daily_settings_service.update_settings(TIMELINE_TYPE, TIMELINE_MODE_ARCADE, values={"chain_length": 10})

        challenge = daily_challenge_service.get_or_create_challenge(_next_date(), TIMELINE_TYPE, TIMELINE_MODE_ARCADE)

        assert len(challenge.spec["cards"]) == 11  # chain_length + 1 (the seed card)
        assert "id" in challenge.spec["cards"][0]
        assert "date" in challenge.spec["cards"][0]


class TestGetOrCreateIsIdempotent:
    def test_second_call_returns_the_same_row(self, daily_challenge_service):
        d = _next_date()

        first = daily_challenge_service.get_or_create_challenge(d, IMMICHDLE_TYPE, MODE_PERSON)
        second = daily_challenge_service.get_or_create_challenge(d, IMMICHDLE_TYPE, MODE_PERSON)

        assert first.id == second.id
        assert first.spec == second.spec

    def test_timeline_two_players_get_the_same_card_sequence(self, daily_challenge_service):
        # "Dos jugadores ven la misma secuencia": the second call is a different player's own
        # request for the same day, not a retry - it must land on the exact same persisted spec
        # rather than generating a fresh chain.
        d = _next_date()

        first = daily_challenge_service.get_or_create_challenge(d, TIMELINE_TYPE, TIMELINE_MODE_ARCADE)
        second = daily_challenge_service.get_or_create_challenge(d, TIMELINE_TYPE, TIMELINE_MODE_ARCADE)

        assert first.id == second.id
        assert first.spec == second.spec


class TestExclusionWindow:
    def test_excludes_the_previous_days_target_within_the_window(self, daily_challenge_service, daily_settings_service):
        daily_settings_service.update_settings(IMMICHDLE_TYPE, MODE_PERSON, values={"no_repeat_days": 3})
        day1 = _next_date()
        day2 = day1 + timedelta(days=1)

        first = daily_challenge_service.get_or_create_challenge(day1, IMMICHDLE_TYPE, MODE_PERSON)
        second = daily_challenge_service.get_or_create_challenge(day2, IMMICHDLE_TYPE, MODE_PERSON)

        assert first.spec["target"]["id"] != second.spec["target"]["id"]

    def test_outside_the_window_repetition_is_allowed(self, daily_challenge_service, daily_settings_service):
        daily_settings_service.update_settings(IMMICHDLE_TYPE, MODE_PERSON, values={"no_repeat_days": 1})
        day1 = _next_date()
        day2 = day1 + timedelta(days=5)  # well outside the 1-day window

        first = daily_challenge_service.get_or_create_challenge(day1, IMMICHDLE_TYPE, MODE_PERSON)
        # Just needs to succeed without raising - day2 isn't excluding day1's target at all, so
        # whatever it picks (possibly even the same person again) is valid.
        second = daily_challenge_service.get_or_create_challenge(day2, IMMICHDLE_TYPE, MODE_PERSON)

        assert first is not None
        assert second is not None

    def test_more_or_less_never_applies_cross_day_exclusion(self, daily_challenge_service, daily_settings_service):
        # MoreOrLess has no no_repeat_days setting at all, so setting an unrelated one shouldn't
        # matter; this just documents/pins that two consecutive days' chains are each generated
        # independently without error.
        daily_settings_service.update_settings(MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS, values={"chain_length": 10})
        day1 = _next_date()
        day2 = day1 + timedelta(days=1)

        first = daily_challenge_service.get_or_create_challenge(day1, MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS)
        second = daily_challenge_service.get_or_create_challenge(day2, MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS)

        assert len(first.spec["chain"]) == 11
        assert len(second.spec["chain"]) == 11

    def test_timeline_excludes_the_previous_days_cards_within_the_window(
        self, daily_challenge_service, daily_settings_service
    ):
        # Unlike MoreOrLess just above, Timeline's own content *is* concrete assets, so it keeps
        # the normal no_repeat_days exclusion on top of its chain_length cap.
        daily_settings_service.update_settings(
            TIMELINE_TYPE, TIMELINE_MODE_ARCADE, values={"chain_length": 10, "no_repeat_days": 3}
        )
        day1 = _next_date()
        day2 = day1 + timedelta(days=1)

        first = daily_challenge_service.get_or_create_challenge(day1, TIMELINE_TYPE, TIMELINE_MODE_ARCADE)
        second = daily_challenge_service.get_or_create_challenge(day2, TIMELINE_TYPE, TIMELINE_MODE_ARCADE)

        first_ids = {card["id"] for card in first.spec["cards"]}
        second_ids = {card["id"] for card in second.spec["cards"]}
        assert first_ids.isdisjoint(second_ids)


class TestFallbackWithoutHistoricalExclusion:
    def test_falls_back_when_the_exclusion_leaves_nothing(
        self, daily_challenge_service, daily_settings_service, immich_service, monkeypatch
    ):
        daily_settings_service.update_settings(IMMICHDLE_TYPE, MODE_PERSON, values={"no_repeat_days": 3})
        day0 = _next_date()
        seeded = daily_challenge_service.get_or_create_challenge(day0, IMMICHDLE_TYPE, MODE_PERSON)
        excluded_id = seeded.spec["target"]["id"]

        real_get_persons = immich_service.get_persons

        def fake_get_persons(*, exclude_ids=frozenset(), **kwargs):
            if excluded_id in {str(i) for i in exclude_ids}:
                return []  # simulates "nothing left once the historical exclusion is applied"
            return real_get_persons(exclude_ids=exclude_ids, **kwargs)

        monkeypatch.setattr(immich_service, "get_persons", fake_get_persons)

        day1 = day0 + timedelta(days=1)
        fallen_back = daily_challenge_service.get_or_create_challenge(day1, IMMICHDLE_TYPE, MODE_PERSON)

        # Falls back to picking *some* target rather than raising - the dev library has more than
        # one named person, so the fallback (no historical exclusion) isn't guaranteed to land back
        # on the same one that was excluded, just to succeed at all instead of erroring out.
        assert fallen_back is not None

    def test_raises_not_enough_content_when_even_the_fallback_fails(
        self, daily_challenge_service, immich_service, monkeypatch
    ):
        monkeypatch.setattr(immich_service, "get_persons", lambda **kwargs: [])

        with pytest.raises(Exception, match="not enough named people"):
            daily_challenge_service.get_or_create_challenge(_next_date(), IMMICHDLE_TYPE, MODE_PERSON)


def _make_reporter(session) -> UserModel:
    unique = uuid.uuid4().hex[:8]
    user = UserModel(
        email=f"daily-report-{unique}@example.com",
        username=f"daily-report-{unique}",
        full_name="Daily Report Test User",
        password_hash="irrelevant",
    )
    session.add(user)
    session.commit()
    return user


class TestReportsExclusion:
    def test_person_target_excludes_a_reported_person(
        self, daily_challenge_service, reports_service, immich_service, db_session
    ):
        people = immich_service.get_persons(named_only=True, limit=2)
        assert len(people) >= 2, "dev data must include at least two named people to exercise this"
        reported, other = people
        reporter = _make_reporter(db_session)
        reports_service.create(reporter.id, "person", reported.id, ["person_name_face_mismatch"], None)

        challenge = daily_challenge_service.get_or_create_challenge(_next_date(), IMMICHDLE_TYPE, MODE_PERSON)

        assert challenge.spec["target"]["id"] != str(reported.id)


class TestConcurrentGeneration:
    def test_two_racing_generations_agree_on_one_challenge(self, immich_service):
        d = _next_date()
        results: dict[str, object] = {}
        barrier = threading.Barrier(2)

        def worker(key: str) -> None:
            session = get_session_factory()()
            try:
                service = DailyChallengeService(session, immich_service)
                barrier.wait(timeout=2)
                results[key] = service.get_or_create_challenge(d, IMMICHDLE_TYPE, MODE_PERSON)
            finally:
                session.close()

        threads = [threading.Thread(target=worker, args=(key,)) for key in ("a", "b")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert results["a"].id == results["b"].id  # type: ignore[union-attr]
