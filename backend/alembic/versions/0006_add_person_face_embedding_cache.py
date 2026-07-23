"""add person_face_embedding_cache table

Cached average face embedding per person (services/ml_service.py's MLSimilarity clue), replacing
an O(n*m) cross-join query. Raw `op.execute` rather than `sa.Column`/`op.create_table` for the
`embedding` column specifically - migrations here stay self-contained (no import of app code, see
persistence/ml_cache.py's hand-rolled `Vector` type, which SQLAlchemy has no built-in equivalent
for), and this table needs the `vector` extension already installed (see
scripts/bootstrap_db_role.py) in this database before this migration can run.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-23

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {_SCHEMA}.person_face_embedding_cache (
            person_id UUID PRIMARY KEY,
            embedding VECTOR(512) NOT NULL,
            face_count INTEGER NOT NULL,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TABLE {_SCHEMA}.person_face_embedding_cache")
