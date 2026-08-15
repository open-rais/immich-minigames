"""In-memory background runner for the admin embedding-cache worker (roadmap #15's "process
missing"/"reprocess all" buttons). One job at a time, state held in a plain Python object - no
persistence, no Redis, no task queue: a single uvicorn worker is the deployment target, the job is
idempotent/re-runnable, and losing progress on a restart is an accepted tradeoff for not adding
infrastructure for a job an admin clicks a button for by hand.

Runs on a plain daemon `threading.Thread`, not asyncio: every query this app makes is synchronous
SQLAlchemy, and converting that (or wrapping each call in `to_thread`) just to run one background
loop isn't worth it. A thread means each entity's queries check a connection out of MLService's
pool and back in between entities (see MLService's own `with engine.connect()` style) rather than
holding one open for the whole run, so a long job doesn't starve the request path's own pool.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from audit import audit
from services.ml_service import MLService

logger = logging.getLogger(__name__)

Entity = Literal["person", "album"]
Scope = Literal["missing", "all"]
JobStatus = Literal["running", "done", "cancelled", "failed"]


class JobAlreadyRunningError(Exception):
    """Raised by EmbeddingJobRunner.start() when a job is already in flight - mapped to 409 by
    api/error_handlers.py."""


def _started_by_field(started_by: str | None) -> dict[str, str]:
    # audit()'s own convention (see auth_service.py's two login_failed call sites): omit an unknown
    # field entirely rather than logging it as null.
    return {"started_by": started_by} if started_by is not None else {}


@dataclass
class EmbeddingJobState:
    """Mutated in place by the background thread as it progresses - a request reading `current`
    mid-run sees a live, possibly slightly stale snapshot (no lock on individual field reads),
    which is fine for a progress bar polled every second, not a transactional read."""

    id: UUID
    entity: Entity
    scope: Scope
    include_ineligible: bool
    status: JobStatus
    total: int
    processed: int = 0
    failed: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    error: str | None = None


class EmbeddingJobRunner:
    """Single-job-at-a-time registry. Takes an MLService instance rather than constructing its
    own: MLService holds two connection pools (persistence/base.py's get_app_engine /
    persistence/immich_db.py's get_immich_engine are NOT memoized themselves - a bare `MLService()`
    here would open a second pair of pools alongside the one the rest of the app already shares
    via api/deps.py's get_ml_service()), so the caller is expected to pass that same instance."""

    def __init__(self, ml_service: MLService) -> None:
        self._ml_service = ml_service
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state: EmbeddingJobState | None = None

    @property
    def current(self) -> EmbeddingJobState | None:
        """The running job, or the last finished one, or None if nothing has ever run."""
        return self._state

    def start(
        self,
        entity: Entity,
        scope: Scope,
        *,
        include_ineligible: bool = False,
        started_by: str | None = None,
    ) -> EmbeddingJobState:
        with self._lock:
            if self._state is not None and self._state.status == "running":
                raise JobAlreadyRunningError(f"a {self._state.entity} embedding job is already running")

            ids, total = self._resolve_ids(entity, scope, include_ineligible)
            state = EmbeddingJobState(
                id=uuid4(),
                entity=entity,
                scope=scope,
                include_ineligible=include_ineligible,
                status="running",
                total=total,
            )
            self._state = state
            self._cancel_event = threading.Event()
            cancel_event = self._cancel_event

        # Runs on the caller's own thread (still inside the request that triggered it, before the
        # background thread below even starts), so it correctly picks up that request's
        # request_id/user via the contextvars audit() merges in - see api/request_context.py.
        # "finished" can't rely on that: it's emitted from the background thread once the request
        # is long gone, so identifying fields (job_id, started_by) are passed explicitly instead.
        audit(
            "embedding_job_started",
            job_id=str(state.id),
            entity=entity,
            scope=scope,
            include_ineligible=include_ineligible,
            total=total,
            **_started_by_field(started_by),
        )

        thread = threading.Thread(
            target=self._run, args=(state, ids, cancel_event, started_by), daemon=True, name="embedding-job"
        )
        self._thread = thread
        thread.start()
        return state

    def _resolve_ids(self, entity: Entity, scope: Scope, include_ineligible: bool) -> tuple[list[UUID], int]:
        stale = (
            self._ml_service.stale_person_ids(eligible_only=not include_ineligible)
            if entity == "person"
            else self._ml_service.stale_album_ids()
        )
        ids = stale.ids if scope == "missing" else stale.all_ids
        return list(ids), stale.total

    def _compute_fn(self, entity: Entity) -> Callable[[UUID, bool], None]:
        target = (
            self._ml_service.compute_person_embedding
            if entity == "person"
            else self._ml_service.compute_album_embedding
        )
        return lambda entity_id, force: target(entity_id, force=force)

    def _run(
        self,
        state: EmbeddingJobState,
        ids: list[UUID],
        cancel_event: threading.Event,
        started_by: str | None,
    ) -> None:
        compute = self._compute_fn(state.entity)
        force = state.scope == "all"
        try:
            for entity_id in ids:
                if cancel_event.is_set():
                    state.status = "cancelled"
                    break
                try:
                    compute(entity_id, force)
                except Exception:
                    # One entity's failure (e.g. it was deleted mid-run) doesn't abort the whole
                    # job - counted and skipped, not raised. Ordinary logging, not audit(): this is
                    # app noise about one row, not an account/security event.
                    logger.exception(
                        "embedding job entity failed", extra={"entity": state.entity, "entity_id": str(entity_id)}
                    )
                    state.failed += 1
                finally:
                    state.processed += 1
            else:
                state.status = "done"
        except Exception as exc:
            # Unlike the per-entity except above, this is the loop/runner itself breaking (a bug,
            # not a bad row) - the whole job is marked failed rather than silently stopping.
            state.status = "failed"
            state.error = str(exc)
        finally:
            state.finished_at = datetime.now(UTC)
            audit(
                "embedding_job_finished",
                job_id=str(state.id),
                entity=state.entity,
                scope=state.scope,
                status=state.status,
                total=state.total,
                processed=state.processed,
                failed=state.failed,
                **_started_by_field(started_by),
            )

    def cancel(self) -> None:
        """No-op if nothing is running - DELETE /admin/workers/embeddings (a future phase) can
        call this unconditionally without checking state first."""
        with self._lock:
            if self._state is None or self._state.status != "running":
                return
            self._cancel_event.set()

    def join(self, timeout: float | None = None) -> None:
        """Blocks until the current job's background thread finishes. Test/shutdown helper -
        nothing in the request path calls this (progress is polled via `current`, not awaited)."""
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def shutdown(self, timeout: float = 5.0) -> None:
        """Called from main.py's lifespan on app shutdown: cancels and waits (bounded) so a long
        job doesn't hang a restart - the thread is daemon anyway, but joining first still gives an
        in-flight entity a chance to finish cleanly instead of being cut off mid-write."""
        self._cancel_event.set()
        self.join(timeout=timeout)
