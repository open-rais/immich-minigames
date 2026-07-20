"""add users.is_admin (ADMIN-FEATURE.md point #1)

Not-null with a server default so no backfill is needed - every existing account starts as a
non-admin, matching the safe default. Promoted at backend startup via ADMIN_EMAIL, see
services/admin_bootstrap.py.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-19

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin", schema=_SCHEMA)
