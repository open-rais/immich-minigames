"""add users.password_changed_at and the invites table

`password_changed_at` backs session revocation (services/auth_service.py's get_user_from_token):
a JWT whose `iat` predates this timestamp is rejected, so changing a password logs out every other
device - the only revocation possible without a server-side session table. NULL for every account
until it changes its password for the first time; that NULL is treated as "nothing to compare
against" (no rejection), so existing accounts aren't affected until they opt in.

`invites` backs registration-by-invitation and admin-initiated password reset - one table,
`kind` distinguishes the two ('invite' | 'password_reset'), consumed via a single atomic
`UPDATE ... RETURNING`. Created here (schema now) even though nothing reads/writes it yet, so the
features that consume it later don't each need their own migration for what's really one small
piece of schema.
`token_hash` is a SHA-256 hex digest, never the token itself - the token
(`secrets.token_urlsafe(32)`) is high-entropy and app-generated, not a human-chosen password, so an
unsalted hash is enough.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )

    op.create_table(
        "invites",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("user_id", postgresql.UUID(), sa.ForeignKey(f"{_SCHEMA}.users.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("invites", schema=_SCHEMA)
    op.drop_column("users", "password_changed_at", schema=_SCHEMA)
