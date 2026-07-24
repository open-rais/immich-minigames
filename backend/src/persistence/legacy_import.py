"""Marker for the one-time migration that moved this app's tables out of a `minigames` schema
inside Immich's database and into this app's own database (see scripts/migrate_legacy_schema.py).

Exactly one row, written in the same transaction as the copied data - so its presence means "the
copy committed", which is what lets a re-run tell apart the two states that otherwise look
identical from the outside: data that this migration imported, versus data an existing install
wrote on its own. Without it, an Immich backup restored *after* migrating (which resurrects the
old schema) would be indistinguishable from a half-finished migration.

A real model rather than a hand-rolled table so `alembic revision --autogenerate` doesn't propose
dropping it.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base


class LegacyImportModel(Base):
    __tablename__ = "legacy_import"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # The database the rows came from - Immich's, i.e. DB_DATABASE_NAME at migration time.
    source_database: Mapped[str]
    # {table_name: row_count} as copied and verified. Kept for forensics: if anything ever looks
    # off later, this is the record of what the migration believed it moved.
    rows_copied: Mapped[dict] = mapped_column(JSONB, default=dict)
    completed_at: Mapped[datetime] = mapped_column(server_default=func.now())
