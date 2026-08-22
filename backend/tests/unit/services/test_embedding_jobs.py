"""Unit tests against a hand-written fake MLService (no mocking library used anywhere in this
codebase) - these are about EmbeddingJobRunner's own concurrency/control-flow contract (one job at
a time, cancellation, per-entity failures not aborting the run), not about real embedding
computation, so a fake that only implements the four methods the runner actually calls is enough."""

import threading
from collections.abc import Callable
from uuid import UUID, uuid4

import pytest

from services.embedding_jobs import EmbeddingJobRunner, JobAlreadyRunningError
from services.ml_service import StaleIds


class _FakeMLService:
    def __init__(
        self,
        ids: list[UUID],
        *,
        fail_ids: frozenset[UUID] = frozenset(),
        on_call: Callable[[UUID], None] | None = None,
    ) -> None:
        self._ids = frozenset(ids)
        self._fail_ids = fail_ids
        self._on_call = on_call
        self.eligible_only_calls: list[bool] = []

    def stale_person_ids(self, *, eligible_only: bool = True) -> StaleIds:
        self.eligible_only_calls.append(eligible_only)
        return StaleIds(ids=self._ids, all_ids=self._ids, total=len(self._ids))

    def stale_album_ids(self) -> StaleIds:
        return StaleIds(ids=self._ids, all_ids=self._ids, total=len(self._ids))

    def invalidate_stale_cache(self) -> None:
        pass

    def compute_person_embedding(self, entity_id: UUID, *, force: bool = False) -> None:
        self._compute(entity_id)

    def compute_album_embedding(self, entity_id: UUID, *, force: bool = False) -> None:
        self._compute(entity_id)

    def _compute(self, entity_id: UUID) -> None:
        if self._on_call is not None:
            self._on_call(entity_id)
        if entity_id in self._fail_ids:
            raise RuntimeError(f"boom on {entity_id}")


class TestStartAndFinish:
    def test_run_processes_every_id_and_finishes_done(self):
        ids = [uuid4(), uuid4(), uuid4()]
        runner = EmbeddingJobRunner(_FakeMLService(ids))

        state = runner.start("person", "missing")
        runner.join(timeout=2)

        assert state is runner.current  # start() returns the same mutable object `current` tracks
        assert runner.current.status == "done"
        assert runner.current.processed == 3
        assert runner.current.failed == 0
        assert runner.current.total == 3

    def test_no_stale_ids_finishes_done_immediately(self):
        runner = EmbeddingJobRunner(_FakeMLService([]))

        runner.start("person", "missing")
        runner.join(timeout=2)

        assert runner.current.status == "done"
        assert runner.current.processed == 0
        assert runner.current.total == 0

    def test_include_ineligible_passes_through_as_eligible_only_false(self):
        ml = _FakeMLService([])
        runner = EmbeddingJobRunner(ml)

        runner.start("person", "missing", include_ineligible=True)
        runner.join(timeout=2)

        assert ml.eligible_only_calls == [False]

    def test_album_entity_dispatches_to_compute_album_embedding(self):
        ids = [uuid4()]
        runner = EmbeddingJobRunner(_FakeMLService(ids))

        runner.start("album", "missing")
        runner.join(timeout=2)

        assert runner.current.status == "done"
        assert runner.current.processed == 1


class TestSecondJobRejected:
    def test_second_start_while_running_raises(self):
        ready = threading.Event()
        release = threading.Event()

        def on_call(_entity_id: UUID) -> None:
            ready.set()
            release.wait(timeout=2)

        runner = EmbeddingJobRunner(_FakeMLService([uuid4(), uuid4()], on_call=on_call))
        runner.start("person", "missing")
        assert ready.wait(timeout=2), "background job never reached its first entity"

        with pytest.raises(JobAlreadyRunningError):
            runner.start("person", "missing")

        release.set()
        runner.join(timeout=2)
        assert runner.current.status == "done"

    def test_a_new_job_is_accepted_once_the_previous_one_finished(self):
        runner = EmbeddingJobRunner(_FakeMLService([uuid4()]))
        runner.start("person", "missing")
        runner.join(timeout=2)
        first_job_id = runner.current.id

        second = runner.start("person", "missing")  # must not raise JobAlreadyRunningError
        runner.join(timeout=2)

        assert second.id != first_job_id
        assert runner.current.status == "done"


class TestCancellation:
    def test_cancel_stops_before_the_next_entity(self):
        ids = [uuid4(), uuid4(), uuid4()]
        runner = EmbeddingJobRunner(_FakeMLService(ids, on_call=lambda _id: runner.cancel()))

        runner.start("person", "missing")
        runner.join(timeout=2)

        assert runner.current.status == "cancelled"
        assert runner.current.processed == 1
        assert runner.current.total == 3

    def test_cancel_with_nothing_running_is_a_no_op(self):
        runner = EmbeddingJobRunner(_FakeMLService([]))

        runner.cancel()  # must not raise

        assert runner.current is None


class TestEntityFailureDoesNotAbortTheRun:
    def test_one_failing_entity_is_counted_and_the_rest_still_process(self):
        ok_id, bad_id, other_ok_id = uuid4(), uuid4(), uuid4()
        runner = EmbeddingJobRunner(_FakeMLService([ok_id, bad_id, other_ok_id], fail_ids=frozenset({bad_id})))

        runner.start("person", "missing")
        runner.join(timeout=2)

        assert runner.current.status == "done"
        assert runner.current.processed == 3
        assert runner.current.failed == 1


class TestShutdown:
    def test_shutdown_cancels_and_joins(self):
        ids = [uuid4(), uuid4(), uuid4()]
        runner = EmbeddingJobRunner(_FakeMLService(ids, on_call=lambda _id: runner.cancel()))
        runner.start("person", "missing")

        runner.shutdown(timeout=2)

        assert runner.current.status == "cancelled"
