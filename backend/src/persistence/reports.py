"""
Own persistence layer for the metadata-reporting feature - a player flags a person/album/asset as
having bad metadata; an admin reviews and resolves reports (see services/reports_service.py).
Shares this app's own database/Base with users.py/games.py (persistence/base.py). Table itself was
created by migration 0014.

`entity_id` deliberately has no FK - it points into Immich's own database, which this app's own
database can't reference across a connection, same reasoning as `UserModel.skin_person_id`.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import SCHEMA, Base


class ReportModel(Base):
    __tablename__ = "reports"
    __table_args__ = (
        # Partial unique: makes a duplicate open report a no-op (INSERT ... ON CONFLICT DO
        # NOTHING in ReportsService.create) without blocking the same (user, entity, reason) from
        # being reported again once a prior report was resolved - rows are never deleted, so a
        # plain UNIQUE would permanently block re-reporting.
        Index(
            "uq_reports_open_per_user",
            "user_id",
            "entity_type",
            "entity_id",
            "reason",
            unique=True,
            postgresql_where=text("NOT solved"),
        ),
        # Backs ReportsService.open_ids_for's exclusion query.
        Index("ix_reports_open_by_reason", "reason", postgresql_where=text("NOT solved")),
        # Backs the admin panel's three paginated, newest-first lists.
        Index("ix_reports_list", "entity_type", "solved", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entity_type: Mapped[str]
    entity_id: Mapped[UUID]
    reason: Mapped[str]
    note: Mapped[str | None] = mapped_column(default=None)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{SCHEMA}.users.id"))
    solved: Mapped[bool] = mapped_column(default=False)
    solved_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
