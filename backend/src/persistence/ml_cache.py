"""
Cached per-person representative face embedding - the average pgvector embedding across a
person's currently visible, non-deleted faces (see services/ml_service.py's
`_get_person_embedding`), avoiding an O(n*m) MAX-over-every-face-pair comparison for
Immichdle's MLSimilarity clue. Lives in this app's own database (see base.py) rather than
Immich's: Immich's database is read-only for this app's DB role (docs/ARCHITECTURE/IMMICH.md), so
a cache we write to has nowhere to go but here - even though the embeddings it's computed from are
read from Immich's `face_search` table.

Freshness is deliberately cheap, not exact: a cached row is considered stale (and recomputed)
whenever `face_count` no longer matches that person's current count of visible, non-deleted
`asset_face` rows. Swapping one face for another without changing the total count is not detected
- accepted imprecision.

`embedding_count` is a second, distinct number: how many vectors actually went into `embedding`
(today always equal to `face_count` for persons, kept as its own column mainly so the two tables
sharing this shape stay structurally identical - see `AlbumEmbeddingCacheModel` below, where the
two numbers genuinely differ). It's the denominator MLService's incremental update needs when
folding newly added faces into the existing average rather than recomputing it from scratch.

`computed_at` is not "when this row was written" - it's the watermark the average is valid *as of*:
taken before any vector was read for this computation, so a face added after that instant is safe
to treat as "not yet counted" even if the write itself lands a moment later. A watermark taken too
early or too late only ever pushes MLService toward a full recompute instead of the incremental
path (wasteful but correct) - it never causes a face to be folded into the average twice or left
out of one that claims to include it. Timezone-aware (`timestamptz`, not the original bare
`timestamp`) because it's compared against Immich's own `asset_face.updatedAt`, on an entirely
different Postgres instance - a naive timestamp has no well-defined meaning across two servers.
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime
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
    embedding_count: Mapped[int]
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now())


class AlbumEmbeddingCacheModel(Base):
    """Cached per-album representative CLIP embedding - the average `smart_search` embedding across
    an album's currently eligible assets (see services/ml_service.py's `_get_album_embedding`),
    powering Albumdle's similarity clue (roadmap #14). Lives in this app's own database for the
    same reason `PersonFaceEmbeddingCacheModel` does (see this module's docstring) - Immich's
    database is read-only for this app's DB role, so a cache this app writes to has nowhere to go
    but here, even though the embeddings it's computed from are read from Immich's `smart_search`
    table (not `face_search` - CLIP image embeddings, not face embeddings).

    Freshness is deliberately cheap, not exact, same contract as the face cache: a cached row is
    considered stale (and recomputed) whenever `asset_count` no longer matches the album's current
    `album_asset` row count. Swapping one asset for another without changing the total count is not
    detected - accepted imprecision, mirroring the face cache's own tradeoff.

    Unlike the face cache, `asset_count` (the raw `album_asset` row count) and `embedding_count`
    (how many vectors actually went into `embedding`) are genuinely different numbers here, not
    just two names for the same thing: the average is only ever taken over assets that are both
    eligible (status/visibility/deletedAt - see _ALBUM_AVG_EMBEDDING_QUERY's standard eligibility
    filter) and have a `smart_search` row, so `embedding_count <= asset_count` in general.
    `embedding_count` is nullable - existing rows from before this column existed have no way to
    know their true value, and NULL there means exactly that: "unknown, don't trust it as an
    incremental-update baseline, recompute in full next time this album is touched." See this
    module's own docstring for what `computed_at` means here too (the same "taken before reading,
    not when written" watermark).

    One row per album that currently has at least one asset. Never queried through an ORM Session
    (MLService holds plain engine connections, not a Session, same as the rest of that module's
    raw-SQL style against Immich's database) - reached via this class's `__table__` with SQLAlchemy
    Core instead."""

    __tablename__ = "album_embedding_cache"

    album_id: Mapped[UUID] = mapped_column(primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    asset_count: Mapped[int]
    embedding_count: Mapped[int | None]
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa.func.now())
