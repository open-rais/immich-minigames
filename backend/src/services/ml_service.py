"""
Immich-ML data access - reads face-embedding data Immich-ML already computed and stored in
Immich's own Postgres (`face_search.embedding`, `vector(512)`, pgvector cosine ops) rather than
calling Immich-ML live - see docs/ARCHITECTURE/IMMICH.md's "face_search" section for why
(immich-machine-learning isn't reachable from the host in the dev stack).
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from persistence.immich_db import get_immich_engine

# MAX(similarity) over every face-pair between the two people, not a single representative-face
# comparison - a single arbitrary/off-angle photo per person could undersell real resemblance,
# which matters for the sibling/family-relative cases this clue is meant to catch. See
# docs/ARCHITECTURE/IMMICH.md's face_search section for the full rationale/precedent
# (immich-power-tools' similar-faces query, which compares one representative face instead).
_FACE_SIMILARITY_QUERY = text("""
    SELECT MAX(1 - (fs_a.embedding <=> fs_b.embedding)) AS similarity
    FROM asset_face fa
    JOIN face_search fs_a ON fs_a."faceId" = fa.id
    JOIN asset_face fb
      ON fb."personId" = :person_b_id
      AND fb."deletedAt" IS NULL AND fb."isVisible"
    JOIN face_search fs_b ON fs_b."faceId" = fb.id
    WHERE fa."personId" = :person_a_id
      AND fa."deletedAt" IS NULL AND fa."isVisible"
""")


class MLService:
    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_immich_engine()

    def face_similarity(self, person_a_id: UUID, person_b_id: UUID) -> float | None:
        """Highest face-similarity (cosine, 0..1) between any face of person_a and any face of
        person_b - None if either has no visible, non-deleted detected faces. Powers Immichdle's
        MLSimilarity clue."""
        if person_a_id == person_b_id:
            return 1.0
        with self._engine.connect() as conn:
            result = conn.execute(
                _FACE_SIMILARITY_QUERY, {"person_a_id": str(person_a_id), "person_b_id": str(person_b_id)}
            ).scalar()
        return float(result) if result is not None else None
