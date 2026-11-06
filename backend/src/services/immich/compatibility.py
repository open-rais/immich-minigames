"""Startup check that the Immich database this app reads is a schema it understands.

The app reads Immich's Postgres directly (see docs/ARCHITECTURE/IMMICH.md), so an Immich version
whose schema differs from what the queries expect wouldn't fail at startup on its own - it would
fail later, as an `UndefinedColumn` on whichever game first touched the changed table. This check
moves that failure to startup, with a message saying what to do about it.

What decides is the **schema**: every column this app reads must exist. The version recorded in
Immich's `version_history` only makes the message readable, and is never a reason to refuse to start
on its own. Immich writes that row from its microservices worker *after* running its migrations,
so for a few seconds right after an upgrade the newest row still names the previous version while
the schema is already the new one.
"""

import logging
import re
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.engine import Connection, Engine

from persistence.immich_tables import metadata, version_history

logger = logging.getLogger(__name__)

MIN_IMMICH_VERSION = (3, 3, 0)

# Columns only ever read through raw SQL (services/ml_service.py - pgvector operators), so they
# aren't part of persistence/immich_tables.py's declarations and have to be listed here.
_RAW_SQL_COLUMNS = frozenset(
    {
        ("asset_face", "updatedAt"),
        ("album_asset", "updatedAt"),
        ("face_search", "faceId"),
        ("face_search", "embedding"),
        ("smart_search", "assetId"),
        ("smart_search", "embedding"),
    }
)


def required_columns() -> frozenset[tuple[str, str]]:
    """Every (table, column) this app reads from Immich's database."""
    declared = {(table.name, column.name) for table in metadata.sorted_tables for column in table.columns}
    return frozenset(declared) | _RAW_SQL_COLUMNS


class ImmichIncompatibleError(RuntimeError):
    """Immich's database lacks columns this app reads - raised at startup, see check_compatibility."""


@dataclass(frozen=True)
class CompatibilityReport:
    missing_columns: frozenset[tuple[str, str]]
    detected_version: str | None  # None when version_history itself is missing or empty

    @property
    def schema_ok(self) -> bool:
        return not self.missing_columns


def parse_version(value: str | None) -> tuple[int, int, int] | None:
    """`"3.3.6"` / `"v3.4.0-rc.2"` -> (major, minor, patch); None if it doesn't look like one."""
    if not value:
        return None
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def _format_min_version() -> str:
    return "v" + ".".join(str(part) for part in MIN_IMMICH_VERSION)


def error_message(report: CompatibilityReport) -> str:
    detected = f"v{report.detected_version}" if report.detected_version else "unknown version"
    missing = ", ".join(f"{table}.{column}" for table, column in sorted(report.missing_columns))
    return (
        f"Immich Minigames requires Immich {_format_min_version()} or newer (detected: {detected}). "
        f"Immich's database is missing columns this app reads: {missing}. "
        "Upgrade Immich, or check that DB_DATABASE_NAME points at Immich's own database."
    )


def _existing_columns(conn: Connection) -> frozenset[tuple[str, str]]:
    # information_schema only lists columns the current role holds some privilege on - fine here,
    # since bootstrap_db_role.py grants this app's role pg_read_all_data on Immich's database.
    rows = conn.execute(
        text("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'")
    )
    return frozenset((row.table_name, row.column_name) for row in rows)


def _latest_version(conn: Connection) -> str | None:
    stmt = select(version_history.c.version).order_by(version_history.c.createdAt.desc()).limit(1)
    return conn.execute(stmt).scalar()


def inspect_compatibility(engine: Engine) -> CompatibilityReport:
    with engine.connect() as conn:
        missing = required_columns() - _existing_columns(conn)
        has_version_table = not any(table == version_history.name for table, _ in missing)
        version = _latest_version(conn) if has_version_table else None
    return CompatibilityReport(missing_columns=frozenset(missing), detected_version=version)


def check_compatibility(engine: Engine) -> None:
    """Raises ImmichIncompatibleError if the schema lacks a column this app reads. A schema that
    is fine but a recorded version below the minimum only logs a warning (see the module
    docstring for why that combination happens right after an upgrade)."""
    report = inspect_compatibility(engine)
    if not report.schema_ok:
        raise ImmichIncompatibleError(error_message(report))

    parsed = parse_version(report.detected_version)
    if parsed is not None and parsed < MIN_IMMICH_VERSION:
        logger.warning(
            "Immich's version_history reports v%s (below the required %s), but its schema has every "
            "column this app reads - most likely Immich was just upgraded and hasn't recorded the "
            "new version yet. Continuing.",
            report.detected_version,
            _format_min_version(),
        )
