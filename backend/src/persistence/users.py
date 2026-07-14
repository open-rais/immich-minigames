"""
Own persistence layer for this app's user accounts (roadmap point B) - entirely separate from
Immich's own users (see docs/ARCHITECTURE/BACKEND.md). Shares the `minigames` schema/Base with
games.py (persistence/base.py) but is not wired to GameModel.owner yet - accounts and the
anonymous-owner game flow coexist independently for now (see services/auth_service.py).
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
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
