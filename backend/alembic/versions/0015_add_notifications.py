"""add notifications tables

Backs Web Push (roadmap point O, F2): device subscriptions, one row of per-account preferences,
and an idempotency log for the scheduler that lands in a later phase - all three land together
since they're one coherent feature, even though `notification_deliveries` isn't read or written
anywhere yet.

`push_subscriptions.user_id` is ON DELETE CASCADE (unlike this app's other FKs, which cascade
ORM-side via relationship(cascade=...)) - a device row has no other owner to clean it up through.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015"
down_revision: Union[str, Sequence[str], None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "minigames"


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(),
            sa.ForeignKey(f"{_SCHEMA}.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(), nullable=False, unique=True),
        sa.Column("p256dh", sa.String(), nullable=False),
        sa.Column("auth", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_push_subscriptions_user",
        "push_subscriptions",
        ["user_id"],
        schema=_SCHEMA,
    )

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", postgresql.UUID(), sa.ForeignKey(f"{_SCHEMA}.users.id"), primary_key=True),
        sa.Column("daily_reminders", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("birthdays", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("album_anniversary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("language", sa.String(), server_default="en", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=_SCHEMA,
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("user_id", postgresql.UUID(), sa.ForeignKey(f"{_SCHEMA}.users.id"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index(
        "uq_notification_deliveries",
        "notification_deliveries",
        ["user_id", "kind", "day"],
        unique=True,
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries", schema=_SCHEMA)
    op.drop_table("notification_preferences", schema=_SCHEMA)
    op.drop_table("push_subscriptions", schema=_SCHEMA)
