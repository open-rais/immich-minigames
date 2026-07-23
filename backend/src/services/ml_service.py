"""
Immich-ML data access - reads face-embedding data Immich-ML already computed and stored in
Immich's own Postgres (`face_search.embedding`, `vector(512)`, pgvector cosine ops) rather than
calling Immich-ML live - see docs/ARCHITECTURE/IMMICH.md's "face_search" section for why
(immich-machine-learning isn't reachable from the host in the dev stack).
"""

from uuid import UUID

import numpy as np
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from persistence.base import get_app_engine
from persistence.immich_db import get_immich_engine
from persistence.ml_cache import PersonFaceEmbeddingCacheModel

_CACHE_TABLE = PersonFaceEmbeddingCacheModel.__table__

# Visible, non-deleted faces are the same eligibility filter used everywhere else a person's faces
# are counted/read (see services/immich_service.py's get_random_asset_with_named_faces).
_FACE_COUNT_QUERY = text("""
    SELECT count(*) FROM asset_face
    WHERE "personId" = :person_id AND "deletedAt" IS NULL AND "isVisible"
""")

# Element-wise average over every visible face's embedding for this person (pgvector's own
# `avg(vector)` aggregate, added in pgvector 0.5+) - a more robust representative embedding than a
# single profile photo, without going back to the O(n*m) cost of comparing every face pair between
# two people (see PersonFaceEmbeddingCacheModel's module docstring). Cast to ::text explicitly so
# the driver hands back a deterministic "[v1,v2,...]" string regardless of whether a pgvector
# adapter is registered on this connection - matches pgvector's own input format, parsed back by
# hand in _get_person_embedding rather than pulling in the `pgvector` package for one read.
_AVG_EMBEDDING_QUERY = text("""
    SELECT avg(fs.embedding)::text
    FROM asset_face af
    JOIN face_search fs ON fs."faceId" = af.id
    WHERE af."personId" = :person_id AND af."deletedAt" IS NULL AND af."isVisible"
""")


def _parse_vector_text(value: str) -> list[float]:
    """Parses pgvector's own `[v1,v2,...]` text output format - see _AVG_EMBEDDING_QUERY."""
    return [float(v) for v in value.strip()[1:-1].split(",")]


class MLService:
    def __init__(self, engine: Engine | None = None, app_engine: Engine | None = None) -> None:
        self._engine = engine or get_immich_engine()
        # This app's own database (not Immich's, which is read-only for this app's DB role) - see
        # persistence/ml_cache.py for why the embedding cache has to live here.
        self._app_engine = app_engine or get_app_engine()

    def _get_person_embedding(self, person_id: UUID) -> np.ndarray | None:
        """This person's representative face embedding - the element-wise average across their
        currently visible, non-deleted faces - served from `person_face_embedding_cache` when
        still fresh (see that table's module docstring for the face-count-based freshness check),
        recomputed and cached otherwise. None if the person currently has no visible faces at all
        (nothing to average, and any stale cache row for them is deleted rather than left behind)."""
        with self._engine.connect() as conn:
            current_count = conn.execute(_FACE_COUNT_QUERY, {"person_id": str(person_id)}).scalar_one()

        if current_count == 0:
            with self._app_engine.begin() as conn:
                conn.execute(sa.delete(_CACHE_TABLE).where(_CACHE_TABLE.c.person_id == person_id))
            return None

        with self._app_engine.connect() as conn:
            cached = conn.execute(
                sa.select(_CACHE_TABLE.c.embedding, _CACHE_TABLE.c.face_count).where(
                    _CACHE_TABLE.c.person_id == person_id
                )
            ).first()
        if cached is not None and cached.face_count == current_count:
            return np.array(cached.embedding, dtype=np.float32)

        with self._engine.connect() as conn:
            avg_text = conn.execute(_AVG_EMBEDDING_QUERY, {"person_id": str(person_id)}).scalar_one()
        embedding = _parse_vector_text(avg_text)

        with self._app_engine.begin() as conn:
            upsert = pg_insert(_CACHE_TABLE).values(
                person_id=person_id, embedding=embedding, face_count=current_count
            )
            upsert = upsert.on_conflict_do_update(
                index_elements=[_CACHE_TABLE.c.person_id],
                set_={
                    "embedding": upsert.excluded.embedding,
                    "face_count": upsert.excluded.face_count,
                    "computed_at": sa.func.now(),
                },
            )
            conn.execute(upsert)

        return np.array(embedding, dtype=np.float32)

    def face_similarity(self, person_a_id: UUID, person_b_id: UUID) -> float | None:
        """Face-similarity (cosine, mathematically -1..1 though unrelated faces usually land near
        0 - slightly negative is normal, not a bug, see docs/ARCHITECTURE/IMMICH.md's face_search
        section) between person_a's and person_b's representative face embeddings (see
        _get_person_embedding) - None if either currently has no visible faces. Powers Immichdle's
        MLSimilarity clue."""
        if person_a_id == person_b_id:
            return 1.0
        embedding_a = self._get_person_embedding(person_a_id)
        embedding_b = self._get_person_embedding(person_b_id)
        if embedding_a is None or embedding_b is None:
            return None
        cosine_similarity = np.dot(embedding_a, embedding_b) / (
            np.linalg.norm(embedding_a) * np.linalg.norm(embedding_b)
        )
        return float(cosine_similarity)
