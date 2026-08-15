"""Admin REST endpoints for the embedding-cache worker - lets an is_admin account see how much of
Persondle's face-similarity cache and Albumdle's similarity cache is warm, and kick off/cancel a
background (re)compute run. Mounted under /admin/workers by api/api.py. Mirrors
api/admin_invites_api.py's shape - same get_current_admin_user dependency."""

from typing import Annotated

from fastapi import APIRouter, Depends

from api.admin_api import get_current_admin_user
from api.deps import get_embedding_job_runner, get_ml_service
from api.dto.admin import EmbeddingCoverageOut, EmbeddingJobOut, EmbeddingWorkersStatusOut, StartEmbeddingJobIn
from persistence.users import UserModel
from services.embedding_jobs import EmbeddingJobRunner
from services.ml_service import MLService, StaleIds

router = APIRouter(prefix="/admin/workers", tags=["admin"])


def _coverage(stale: StaleIds) -> EmbeddingCoverageOut:
    return EmbeddingCoverageOut(cached=stale.total - len(stale.ids), total=stale.total)


# No @limiter.limit here, unlike most of api/api.py's routes: the admin panel polls this every
# ~1s while a job is running to drive its progress bar, and a per-minute cap would break that. It
# only reads memory (the job registry) plus two cheap count queries, no Immich REST calls and no
# writes to the embedding cache - the same "admin-only, no limiter" posture every other router in
# this module already has (see api/admin_daily_api.py, api/admin_games_api.py).
@router.get("/embeddings", response_model=EmbeddingWorkersStatusOut)
def get_embedding_workers_status(
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    ml_service: Annotated[MLService, Depends(get_ml_service)],
    runner: Annotated[EmbeddingJobRunner, Depends(get_embedding_job_runner)],
) -> EmbeddingWorkersStatusOut:
    persons = ml_service.stale_person_ids(eligible_only=True)
    albums = ml_service.stale_album_ids()
    job = runner.current
    return EmbeddingWorkersStatusOut(
        persons=_coverage(persons),
        albums=_coverage(albums),
        job=EmbeddingJobOut.from_state(job) if job is not None else None,
    )


@router.post("/embeddings", response_model=EmbeddingJobOut, status_code=202)
def start_embedding_job(
    body: StartEmbeddingJobIn,
    admin: Annotated[UserModel, Depends(get_current_admin_user)],
    runner: Annotated[EmbeddingJobRunner, Depends(get_embedding_job_runner)],
) -> EmbeddingJobOut:
    # JobAlreadyRunningError propagates to api/error_handlers.py's 409 mapping - no try/except
    # here, same convention as every other route in this app.
    state = runner.start(body.entity, body.scope, include_ineligible=body.include_ineligible, started_by=admin.username)
    return EmbeddingJobOut.from_state(state)


@router.delete("/embeddings", status_code=204)
def cancel_embedding_job(
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    runner: Annotated[EmbeddingJobRunner, Depends(get_embedding_job_runner)],
) -> None:
    runner.cancel()
