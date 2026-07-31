"""
Own persistence layer for invitations and admin-initiated password resets - one table, `kind`
distinguishes the two ('invite' | 'password_reset'), consumed via a single atomic
UPDATE...RETURNING (see services/invite_service.py). Shares this app's own database/Base with
users.py/games.py (persistence/base.py). Table itself was created by migration 0010 (alongside
users.password_changed_at).
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import SCHEMA, Base


class InviteModel(Base):
    __tablename__ = "invites"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(unique=True)
    kind: Mapped[str]
    # Only set for kind="password_reset" - which account the reset applies to. NULL for
    # kind="invite", which isn't tied to any existing account.
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.users.id"), default=None)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
