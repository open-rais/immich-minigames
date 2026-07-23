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

# Single representative-face comparison (each person's own profile/thumbnail face,
# person."faceAssetId") rather than MAX over every face-pair cross join - O(1) two indexed
# lookups instead of O(n*m) faces-per-person, same pattern immich-power-tools' similar-faces query
# uses. See docs/ARCHITECTURE/IMMICH.md's face_search section for the precedent/rationale and why
# this replaced the earlier cross-join version.
_FACE_SIMILARITY_QUERY = text("""
    SELECT 1 - (fs_a.embedding <=> fs_b.embedding) AS similarity
    FROM person pa
    JOIN face_search fs_a ON fs_a."faceId" = pa."faceAssetId"
    JOIN person pb ON pb.id = :person_b_id
    JOIN face_search fs_b ON fs_b."faceId" = pb."faceAssetId"
    WHERE pa.id = :person_a_id
""")


class MLService:
    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_immich_engine()

    def face_similarity(self, person_a_id: UUID, person_b_id: UUID) -> float | None:
        """Face-similarity (cosine, mathematically -1..1 though unrelated faces usually land near
        0 - slightly negative is normal, not a bug, see docs/ARCHITECTURE/IMMICH.md's face_search
        section) between person_a's and person_b's profile face (person.faceAssetId - the same
        face Immich shows as that person's thumbnail) - None if either has no profile face set.
        Powers Immichdle's MLSimilarity clue."""
        if person_a_id == person_b_id:
            return 1.0
        with self._engine.connect() as conn:
            result = conn.execute(
                _FACE_SIMILARITY_QUERY, {"person_a_id": str(person_a_id), "person_b_id": str(person_b_id)}
            ).scalar()
        return float(result) if result is not None else None
