"""
Own persistence layer for this app's user accounts (roadmap point B) - entirely separate from
Immich's own users (see docs/ARCHITECTURE/BACKEND.md). Shares the `minigames` schema/Base with
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
    # user circle. Deliberately not a FK - Immich's `person` table lives in the separate, read-only
    # `public` schema this app never references via FK (see docs/ARCHITECTURE/BACKEND.md); multiple
    # accounts may pick the same person, it's purely decorative and not identity-linked.
    skin_person_id: Mapped[UUID | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
