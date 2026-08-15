"""add embedding_count to person_face_embedding_cache and album_embedding_cache, make computed_at
timezone-aware

Separates "how many vectors actually went into the cached average" from the existing freshness
fingerprint (face_count / asset_count), which they've stopped being interchangeable with: the
incremental weighted-average update (services/ml_service.py) needs the true vector count as its
denominator, and for albums that's never been the same number as asset_count (asset_count is the
raw album_asset row count; the average is only ever taken over eligible assets that also have a
smart_search row - see _ALBUM_AVG_EMBEDDING_QUERY).

For persons the two counts have always been identical (face_count and embedding_count use the same
"visible, non-deleted, has a face_search row" filter), so every existing row backfills cleanly and
the column goes NOT NULL immediately. Albums have no such equivalence to backfill from - existing
rows get NULL, which the application treats as "unknown, recompute in full" the next time that
album is touched, exactly the right behavior for a value nobody can currently reconstruct without
re-running the average.

`computed_at` also switches from `timestamp` (no zone) to `timestamptz`: it now doubles as the
watermark compared against Immich's own `updatedAt` columns (both `timestamptz`, on a *different*
Postgres instance) to tell which faces/assets are new since the cache row was last computed - a
naive timestamp has no defined meaning across two servers. Both databases run with `Etc/UTC` as
their session timezone (confirmed against the dev stack), so existing naive values convert losslessly
by reinterpreting them as UTC.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-15

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.add_column(
        "person_face_embedding_cache",
        sa.Column("embedding_count", sa.Integer(), nullable=True),
        schema=_SCHEMA,
    )
    op.execute(f"UPDATE {_SCHEMA}.person_face_embedding_cache SET embedding_count = face_count")
    op.alter_column("person_face_embedding_cache", "embedding_count", nullable=False, schema=_SCHEMA)

    op.add_column(
        "album_embedding_cache",
        sa.Column("embedding_count", sa.Integer(), nullable=True),
        schema=_SCHEMA,
    )

    for table in ("person_face_embedding_cache", "album_embedding_cache"):
        op.execute(
            f"ALTER TABLE {_SCHEMA}.{table} "
            f"ALTER COLUMN computed_at TYPE timestamptz USING computed_at AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    for table in ("person_face_embedding_cache", "album_embedding_cache"):
        op.execute(
            f"ALTER TABLE {_SCHEMA}.{table} "
            f"ALTER COLUMN computed_at TYPE timestamp USING computed_at AT TIME ZONE 'UTC'"
        )

    op.drop_column("album_embedding_cache", "embedding_count", schema=_SCHEMA)
    op.drop_column("person_face_embedding_cache", "embedding_count", schema=_SCHEMA)
