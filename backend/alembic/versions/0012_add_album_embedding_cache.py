"""add album_embedding_cache table

Cached average CLIP embedding per album (services/ml_service.py's Albumdle similarity clue,
roadmap #14) - averaged from Immich's own `smart_search` table (semantic/text-search embeddings,
not `face_search`) across an album's assets, mirroring person_face_embedding_cache's shape and
role exactly (see 0006). Raw `op.execute` for the same reason as 0006: migrations here stay
self-contained (no import of app code, see persistence/ml_cache.py's `AlbumEmbeddingCacheModel`
reusing that same module's hand-rolled `Vector` type), and this table needs the `vector` extension
already installed (0006 already did this in this app's own database).

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-31

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {_SCHEMA}.album_embedding_cache (
            album_id UUID PRIMARY KEY,
            embedding VECTOR(512) NOT NULL,
            asset_count INTEGER NOT NULL,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TABLE {_SCHEMA}.album_embedding_cache")
