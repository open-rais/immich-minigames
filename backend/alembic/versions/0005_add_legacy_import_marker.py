"""add legacy_import marker table

Records that scripts/migrate_legacy_schema.py copied this app's tables out of the `minigames`
schema inside Immich's database and into this app's own database. Written in the same transaction
as the copied rows, so its presence means the copy committed - see persistence/legacy_import.py.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.create_table(
        "legacy_import",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_database", sa.String(), nullable=False),
        sa.Column("rows_copied", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("completed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("legacy_import", schema=_SCHEMA)
