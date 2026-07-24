"""
Own persistence layer for this app's user accounts (roadmap point B) - entirely separate from
Immich's own users (see docs/ARCHITECTURE/BACKEND.md). Shares this app's own database/Base with
games.py (persistence/base.py). GameModel.user_id (roadmap point E) links a game to its account
when the creating request was authenticated - the anonymous-owner flow still works unchanged for
logged-out play (see services/games_service.py).
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(unique=True)
    username: Mapped[str] = mapped_column(unique=True)
    full_name: Mapped[str]
    password_hash: Mapped[str]
    # Cosmetic avatar (roadmap point E): a Person id from the Immich library, shown in the header's
    # user circle. Deliberately not a FK - and now it couldn't be one even in principle: Immich's
    # `person` table lives in a different Postgres database, which foreign keys cannot span (see
    # docs/ARCHITECTURE/BACKEND.md). Multiple accounts may pick the same person, it's purely
    # decorative and not identity-linked.
    skin_person_id: Mapped[UUID | None] = mapped_column(default=None)
    # Admin feature (ADMIN-FEATURE.md point #1) - promoted via ADMIN_EMAIL at backend startup
    # (see services/admin_bootstrap.py), never set through a registration/profile endpoint.
    is_admin: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
