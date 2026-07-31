"""
Cached per-album representative CLIP embedding - the average `smart_search` embedding across an
album's currently eligible assets (see services/ml_service.py's `_get_album_embedding`), powering
Albumdle's similarity clue (roadmap #14). Lives in this app's own database for the same reason
person_face_embedding_cache does (see that table's module docstring, persistence/ml_cache.py) -
Immich's database is read-only for this app's DB role, so a cache this app writes to has nowhere
to go but here, even though the embeddings it's computed from are read from Immich's
`smart_search` table (not `face_search` - CLIP image embeddings, not face embeddings).

Freshness is deliberately cheap, not exact, same contract as the face cache: a cached row is
considered stale (and recomputed) whenever `asset_count` no longer matches the album's current
`album_asset` row count. Swapping one asset for another without changing the total count is not
detected - accepted imprecision, mirroring the face cache's own tradeoff.
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base
from persistence.ml_cache import EMBEDDING_DIM, Vector


class AlbumEmbeddingCacheModel(Base):
    """One row per album that currently has at least one asset - see module docstring for the
    freshness contract. Never queried through an ORM Session (MLService holds plain engine
    connections, not a Session, same as the rest of that module's raw-SQL style against Immich's
    database) - reached via this class's `__table__` with SQLAlchemy Core instead."""

    __tablename__ = "album_embedding_cache"

    album_id: Mapped[UUID] = mapped_column(primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    asset_count: Mapped[int]
    computed_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
