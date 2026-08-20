"""add reports table

Backs the metadata-reporting feature: players flag a person/album/asset as having bad metadata.
`entity_id` has no FK because it points into Immich's own database, which this app's database
can't reference across a connection - same reasoning as `users.skin_person_id`.

Three indexes:
- `uq_reports_open_per_user` - partial unique on (user_id, entity_type, entity_id, reason) WHERE
  NOT solved. Makes a duplicate open report a no-op (INSERT ... ON CONFLICT DO NOTHING), while
  still allowing the same (user, entity, reason) to be reported again after a prior report was
  resolved - the row is never deleted, `solved` just flips back to eligible.
- `ix_reports_open_by_reason` - partial on (reason) WHERE NOT solved, backs the exclusion query
  that will filter live round generation by open reports (not implemented yet).
- `ix_reports_list` - on (entity_type, solved, created_at), backs the admin panel's three
  paginated, newest-first lists.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014"
down_revision: Union[str, Sequence[str], None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("user_id", postgresql.UUID(), sa.ForeignKey(f"{_SCHEMA}.users.id"), nullable=False),
        sa.Column("solved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("solved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index(
        "uq_reports_open_per_user",
        "reports",
        ["user_id", "entity_type", "entity_id", "reason"],
        unique=True,
        schema=_SCHEMA,
        postgresql_where=sa.text("NOT solved"),
    )
    op.create_index(
        "ix_reports_open_by_reason",
        "reports",
        ["reason"],
        schema=_SCHEMA,
        postgresql_where=sa.text("NOT solved"),
    )
    op.create_index(
        "ix_reports_list",
        "reports",
        ["entity_type", "solved", "created_at"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("reports", schema=_SCHEMA)
