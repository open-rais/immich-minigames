import uuid
from dataclasses import dataclass, field

import pytest

from persistence.users import UserModel
from services.reports_service import (
    InvalidReportReasonError,
    ReportExclusions,
    ReportNotFoundError,
    ReportsService,
)


@dataclass
class _Entity:
    id: uuid.UUID


@dataclass
class _Face:
    asset_id: uuid.UUID
    person_id: uuid.UUID


@dataclass
class _FakeContentQueries:
    """Minimal ContentQueries double for TestFilterFor - a plain in-memory pool per entity type,
    filtered/looked-up exactly the way the real ImmichService methods behave for the two things
    the wrapper cares about (`ids=` vs `exclude_ids=`), plus a call log so a test can assert how
    many times a method actually ran (the fallback-retry tests need that)."""

    asset_pool: list[_Entity] = field(default_factory=list)
    person_pool: list[_Entity] = field(default_factory=list)
    album_pool: list[_Entity] = field(default_factory=list)
    face_pool: list[_Face] = field(default_factory=list)
    calls: list[tuple[str, dict]] = field(default_factory=list)

    def get_assets(self, *, ids=None, exclude_ids=frozenset(), **kwargs):
        self.calls.append(("get_assets", {"ids": ids, "exclude_ids": exclude_ids, **kwargs}))
        if ids is not None:
            return [a for a in self.asset_pool if a.id in ids]
        return [a for a in self.asset_pool if a.id not in exclude_ids]

    def get_persons(self, *, ids=None, exclude_ids=frozenset(), **kwargs):
        self.calls.append(("get_persons", {"ids": ids, "exclude_ids": exclude_ids, **kwargs}))
        if ids is not None:
            return [p for p in self.person_pool if p.id in ids]
        return [p for p in self.person_pool if p.id not in exclude_ids]

    def get_albums(self, *, ids=None, exclude_ids=frozenset(), **kwargs):
        self.calls.append(("get_albums", {"ids": ids, "exclude_ids": exclude_ids, **kwargs}))
        if ids is not None:
            return [a for a in self.album_pool if a.id in ids]
        return [a for a in self.album_pool if a.id not in exclude_ids]

    def get_random_asset_with_named_faces(self, *, exclude_asset_ids=frozenset(), exclude_person_ids=frozenset()):
        self.calls.append(
            (
                "get_random_asset_with_named_faces",
                {"exclude_asset_ids": exclude_asset_ids, "exclude_person_ids": exclude_person_ids},
            )
        )
        return [
            f
            for f in self.face_pool
            if f.asset_id not in exclude_asset_ids and f.person_id not in exclude_person_ids
        ]

    def search_persons(self, query):
        # Stands in for anything the wrapper doesn't override (thumbnails, search_*, per-id clue
        # queries) - proves __getattr__ forwards unfiltered.
        return f"searched:{query}"


def _make_user(session) -> uuid.UUID:
    unique = uuid.uuid4().hex[:8]
    user = UserModel(
        email=f"reports-{unique}@example.com",
        username=f"reports-{unique}",
        full_name="Reports Test User",
        password_hash="irrelevant",
    )
    session.add(user)
    session.commit()
    return user.id


class TestCreate:
    def test_duplicate_open_report_is_a_no_op(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        entity_id = uuid.uuid4()

        service.create(user_id, "asset", entity_id, ["asset_date"], None)
        service.create(user_id, "asset", entity_id, ["asset_date"], None)

        reports = service.list("asset", solved=False)
        matching = [r for r in reports if r.entity_id == entity_id and r.reason == "asset_date"]
        assert len(matching) == 1

    def test_multiple_reasons_in_one_call_creates_one_row_each(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        entity_id = uuid.uuid4()

        service.create(user_id, "person", entity_id, ["person_birth_date", "person_name_spelling"], None)

        reports = service.list("person", solved=False)
        matching = {r.reason for r in reports if r.entity_id == entity_id}
        assert matching == {"person_birth_date", "person_name_spelling"}

    def test_reporting_again_after_resolution_creates_a_new_row(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        entity_id = uuid.uuid4()
        service.create(user_id, "album", entity_id, ["album_name_spelling"], None)
        [report] = [r for r in service.list("album", solved=False) if r.entity_id == entity_id]
        service.set_solved(report.id, True)

        service.create(user_id, "album", entity_id, ["album_name_spelling"], None)

        open_reports = [r for r in service.list("album", solved=False) if r.entity_id == entity_id]
        assert len(open_reports) == 1
        assert open_reports[0].id != report.id


class TestCreateValidatesReason:
    def test_reason_that_does_not_belong_to_entity_type_raises(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)

        with pytest.raises(InvalidReportReasonError):
            service.create(user_id, "person", uuid.uuid4(), ["asset_date"], None)

    def test_a_rejected_call_inserts_nothing_even_for_the_valid_reasons_in_it(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        entity_id = uuid.uuid4()

        with pytest.raises(InvalidReportReasonError):
            service.create(user_id, "person", entity_id, ["person_birth_date", "asset_date"], None)

        assert entity_id not in {r.entity_id for r in service.list("person", solved=False)}


class TestList:
    def test_filters_by_entity_type_and_solved(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        open_id, solved_id, other_type_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        service.create(user_id, "asset", open_id, ["asset_location"], None)
        service.create(user_id, "asset", solved_id, ["asset_location"], None)
        service.create(user_id, "person", other_type_id, ["person_birth_date"], None)
        [solved_report] = [r for r in service.list("asset", solved=False) if r.entity_id == solved_id]
        service.set_solved(solved_report.id, True)

        open_reports = service.list("asset", solved=False)
        solved_reports = service.list("asset", solved=True)

        assert open_id in {r.entity_id for r in open_reports}
        assert solved_id not in {r.entity_id for r in open_reports}
        assert solved_id in {r.entity_id for r in solved_reports}
        assert all(r.entity_type == "asset" for r in open_reports + solved_reports)

    def test_orders_newest_first_and_respects_offset_limit(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        ids = [uuid.uuid4() for _ in range(3)]
        for entity_id in ids:
            service.create(user_id, "asset", entity_id, ["asset_face_mismatch"], None)

        reports = service.list("asset", solved=False, limit=1000)
        # newest created (last inserted) must sort before older ones among our own rows
        our_reports_in_order = [r.entity_id for r in reports if r.entity_id in ids]
        assert our_reports_in_order == list(reversed(ids))

        page = service.list("asset", solved=False, offset=1, limit=1)
        assert len(page) == 1


class TestCounts:
    def test_counts_only_open_reports_grouped_by_entity_type(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        asset_id, person_id = uuid.uuid4(), uuid.uuid4()
        service.create(user_id, "asset", asset_id, ["asset_location"], None)
        service.create(user_id, "person", person_id, ["person_birth_date"], None)
        [solved_person_report] = [r for r in service.list("person", solved=False) if r.entity_id == person_id]
        service.set_solved(solved_person_report.id, True)

        counts = service.counts()

        assert counts.get("asset", 0) >= 1
        # the only person report we made is now resolved; if it were the only one in the table,
        # "person" wouldn't appear at all - either way its open count from our own rows is zero
        assert person_id not in {r.entity_id for r in service.list("person", solved=False)}


class TestSetSolved:
    def test_unknown_id_raises(self, db_session):
        service = ReportsService(db_session)

        with pytest.raises(ReportNotFoundError):
            service.set_solved(uuid.uuid4(), True)

    def test_resolving_sets_solved_at(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        entity_id = uuid.uuid4()
        service.create(user_id, "asset", entity_id, ["asset_date"], None)
        [report] = [r for r in service.list("asset", solved=False) if r.entity_id == entity_id]

        resolved = service.set_solved(report.id, True)

        assert resolved.solved is True
        assert resolved.solved_at is not None

    def test_reverting_clears_solved_at(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        entity_id = uuid.uuid4()
        service.create(user_id, "asset", entity_id, ["asset_date"], None)
        [report] = [r for r in service.list("asset", solved=False) if r.entity_id == entity_id]
        service.set_solved(report.id, True)

        reverted = service.set_solved(report.id, False)

        assert reverted.solved is False
        assert reverted.solved_at is None


class TestOpenIdsFor:
    def test_groups_ids_by_entity_type(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        asset_id, person_id, album_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        service.create(user_id, "asset", asset_id, ["asset_date"], None)
        service.create(user_id, "person", person_id, ["person_birth_date"], None)
        service.create(user_id, "album", album_id, ["album_cover_mismatch"], None)

        exclusions = service.open_ids_for(["asset_date", "person_birth_date", "album_cover_mismatch"])

        assert asset_id in exclusions.asset_ids
        assert person_id in exclusions.person_ids
        assert album_id in exclusions.album_ids

    def test_reason_with_no_reports_returns_empty(self, db_session):
        service = ReportsService(db_session)

        exclusions = service.open_ids_for([f"nonexistent-{uuid.uuid4().hex}"])

        assert exclusions == ReportExclusions()

    def test_empty_reasons_returns_empty_without_matching_anything(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        entity_id = uuid.uuid4()
        service.create(user_id, "asset", entity_id, ["asset_date"], None)

        exclusions = service.open_ids_for([])

        assert exclusions == ReportExclusions()

    def test_solved_report_is_excluded_from_results(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        entity_id = uuid.uuid4()
        service.create(user_id, "asset", entity_id, ["asset_date"], None)
        [report] = [r for r in service.list("asset", solved=False) if r.entity_id == entity_id]
        service.set_solved(report.id, True)

        exclusions = service.open_ids_for(["asset_date"])

        assert entity_id not in exclusions.asset_ids


class TestFilterFor:
    def test_returns_unwrapped_for_an_unregistered_game_mode(self, db_session):
        service = ReportsService(db_session)
        fake = _FakeContentQueries()

        result = service.filter_for(fake, "not-a-real-game", "not-a-real-mode")

        assert result is fake

    def test_returns_unwrapped_when_no_open_reports_apply(self, db_session):
        service = ReportsService(db_session)
        # geoguessr/distanceBetweenGuess is a real registered mode (excluded by asset_location) -
        # the DB is shared and never reset between tests (see conftest.py), so other tests in this
        # same file leave open asset_location reports behind. Resolve them first, so this test's
        # "nothing is currently open" premise holds regardless of run order.
        for report in service.list("asset", solved=False, limit=1000):
            if report.reason == "asset_location":
                service.set_solved(report.id, True)
        fake = _FakeContentQueries()

        result = service.filter_for(fake, "geoguessr", "distanceBetweenGuess")

        assert result is fake

    def test_returns_wrapped_when_a_relevant_open_report_exists(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        service.create(user_id, "asset", uuid.uuid4(), ["asset_location"], None)
        fake = _FakeContentQueries()

        result = service.filter_for(fake, "geoguessr", "distanceBetweenGuess")

        assert result is not fake

    def test_filters_reported_assets_out_of_sampling(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        reported_id, other_id = uuid.uuid4(), uuid.uuid4()
        service.create(user_id, "asset", reported_id, ["asset_location"], None)
        fake = _FakeContentQueries(asset_pool=[_Entity(reported_id), _Entity(other_id)])

        wrapped = service.filter_for(fake, "geoguessr", "distanceBetweenGuess")
        result = wrapped.get_assets(limit=10)

        assert {a.id for a in result} == {other_id}

    def test_ids_bypasses_filtering(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        reported_id = uuid.uuid4()
        service.create(user_id, "asset", reported_id, ["asset_location"], None)
        fake = _FakeContentQueries(asset_pool=[_Entity(reported_id)])

        wrapped = service.filter_for(fake, "geoguessr", "distanceBetweenGuess")
        result = wrapped.get_assets(ids=frozenset({reported_id}))

        assert {a.id for a in result} == {reported_id}

    def test_fallback_retries_without_exclusion_when_the_pool_is_fully_reported(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        reported_id = uuid.uuid4()
        service.create(user_id, "asset", reported_id, ["asset_location"], None)
        fake = _FakeContentQueries(asset_pool=[_Entity(reported_id)])

        wrapped = service.filter_for(fake, "geoguessr", "distanceBetweenGuess")
        result = wrapped.get_assets(limit=10)

        assert {a.id for a in result} == {reported_id}
        assert [call for call, _ in fake.calls].count("get_assets") == 2

    def test_no_retry_when_the_first_sample_already_returns_something(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        reported_id, other_id = uuid.uuid4(), uuid.uuid4()
        service.create(user_id, "asset", reported_id, ["asset_location"], None)
        fake = _FakeContentQueries(asset_pool=[_Entity(reported_id), _Entity(other_id)])

        wrapped = service.filter_for(fake, "geoguessr", "distanceBetweenGuess")
        wrapped.get_assets(limit=10)

        assert [call for call, _ in fake.calls].count("get_assets") == 1

    def test_exclude_person_ids_is_threaded_into_get_random_asset_with_named_faces(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        reported_person_id, other_person_id = uuid.uuid4(), uuid.uuid4()
        service.create(user_id, "person", reported_person_id, ["person_name_face_mismatch"], None)
        asset_a, asset_b = uuid.uuid4(), uuid.uuid4()
        fake = _FakeContentQueries(
            face_pool=[_Face(asset_a, reported_person_id), _Face(asset_b, other_person_id)]
        )

        wrapped = service.filter_for(fake, "whos-that-person", "namedFaces")
        result = wrapped.get_random_asset_with_named_faces()

        assert {f.person_id for f in result} == {other_person_id}

    def test_unfiltered_methods_pass_through_via_getattr(self, db_session):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        service.create(user_id, "asset", uuid.uuid4(), ["asset_location"], None)
        fake = _FakeContentQueries()

        wrapped = service.filter_for(fake, "geoguessr", "distanceBetweenGuess")

        assert wrapped.search_persons("bob") == "searched:bob"


class TestAuditEvents:
    def test_create_emits_report_created(self, db_session, audit_log):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        entity_id = uuid.uuid4()

        service.create(user_id, "asset", entity_id, ["asset_date", "asset_location"], "looks wrong")

        record = next(r for r in audit_log.records if r.event == "report_created")
        assert record.entity_type == "asset"
        assert record.entity_id == str(entity_id)
        assert record.reasons == ["asset_date", "asset_location"]
        assert record.user_id == str(user_id)

    def test_set_solved_emits_report_resolved_in_both_directions(self, db_session, audit_log):
        service = ReportsService(db_session)
        user_id = _make_user(db_session)
        entity_id = uuid.uuid4()
        service.create(user_id, "asset", entity_id, ["asset_date"], None)
        [report] = [r for r in service.list("asset", solved=False) if r.entity_id == entity_id]
        audit_log.clear()

        service.set_solved(report.id, True)
        service.set_solved(report.id, False)

        events = [r for r in audit_log.records if r.event == "report_resolved"]
        assert [e.solved for e in events] == [True, False]
