"""
Cached per-person representative face embedding - the average pgvector embedding across a
person's currently visible, non-deleted faces (see services/ml_service.py's
`_get_person_embedding`), replacing an earlier O(n*m) MAX-over-every-face-pair query for
Immichdle's MLSimilarity clue. Lives in this app's own database (see base.py) rather than
Immich's: Immich's database is read-only for this app's DB role (docs/ARCHITECTURE/IMMICH.md), so
a cache we write to has nowhere to go but here - even though the embeddings it's computed from are
read from Immich's `face_search` table.

Freshness is deliberately cheap, not exact: a cached row is considered stale (and recomputed)
whenever `face_count` no longer matches that person's current count of visible, non-deleted
`asset_face` rows. Swapping one face for another without changing the total count is not detected
- accepted imprecision, confirmed with the project owner.
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base

# Must match face_search.embedding's dimension in Immich's own database (confirmed via `\d
# face_search` against the dev stack: vector(512)) - this cache stores an element-wise average of
# those same vectors, so the dimension has to agree.
EMBEDDING_DIM = 512


class Vector(sa.types.UserDefinedType):
    """Minimal Postgres pgvector column type - just enough to declare `vector(n)` DDL and
    round-trip a plain Python list of floats through it as `[v1,v2,...]` text (pgvector's own
    input/output format). Hand-rolled instead of taking a dependency on the `pgvector` package:
    this app only ever needs one such column, read/written as a plain sequence - not that
    package's numpy/asyncpg adapters or ANN-index query helpers, none of which apply here (this
    table is only ever looked up by its `person_id` primary key, never searched by similarity)."""

    cache_ok = True

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def get_col_spec(self, **kw: object) -> str:
        return f"vector({self.dim})"

    def bind_processor(self, dialect: sa.engine.Dialect):
        def process(value: list[float] | None) -> str | None:
            if value is None:
                return None
            return "[" + ",".join(repr(float(v)) for v in value) + "]"

        return process

    def result_processor(self, dialect: sa.engine.Dialect, coltype: object):
        def process(value: str | None) -> list[float] | None:
            if value is None:
                return None
            return [float(v) for v in value.strip()[1:-1].split(",")]

        return process


class PersonFaceEmbeddingCacheModel(Base):
    """One row per person who currently has at least one visible face - see module docstring for
    the freshness contract. Never queried through an ORM Session (MLService holds plain engine
    connections, not a Session, same as the rest of that module's raw-SQL style against Immich's
    database) - reached via this class's `__table__` with SQLAlchemy Core instead."""

    __tablename__ = "person_face_embedding_cache"

    person_id: Mapped[UUID] = mapped_column(primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    face_count: Mapped[int]
    computed_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
