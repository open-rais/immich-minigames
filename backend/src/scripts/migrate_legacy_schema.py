"""One-time migration: moves this app's tables out of the `minigames` schema inside Immich's own
database and into this app's own database.

Why this exists: Immich backs up with `pg_dump --clean --if-exists` scoped to its own database, so
anything living in there is swept into Immich's dumps. On restore, the dump's `DROP SCHEMA IF
EXISTS minigames` fails against any table created *after* that backup was taken (it isn't in the
dump, so it isn't dropped first, and it blocks the drop) - and since Immich restores with
`--single-transaction --set ON_ERROR_STOP=on`, the whole restore aborts. Immich also rewrites every
`OWNER TO` in the dump to its own DB user, so even a clean restore would leave the tables with the
wrong owner. A separate database is outside `pg_dump`'s scope entirely.

Called from scripts/bootstrap_db_role.py, the only component holding Immich's admin credentials -
and therefore the only one able to drop a schema the app's own role does not own.

Safety model, in order: nothing is destroyed before its replacement is committed AND verified.
The copy lands in a single target transaction whose row counts are checked before commit; the
source is read through one REPEATABLE READ snapshot so counts and data cannot disagree; the source
is re-counted after commit to catch a writer that slipped in; and the schema's contents are
enumerated and matched against a known set before `DROP ... CASCADE` is allowed to run at all.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

# Copied in foreign-key dependency order: games.user_id -> users.id, rounds.game_id -> games.id.
# game_settings is standalone. legacy_import is deliberately absent - it's this migration's own
# marker, created fresh in the target by Alembic 0005, never copied.
LEGACY_TABLES: tuple[str, ...] = ("users", "games", "rounds", "game_settings")

# Everything the legacy schema is allowed to contain. `DROP SCHEMA ... CASCADE` is unbounded by
# definition; matching against this set is what bounds it. Anything else (a view, a stray table
# someone added, a function) means we don't understand what we're about to delete, so we refuse.
KNOWN_LEGACY_TABLES: frozenset[str] = frozenset(LEGACY_TABLES) | {"alembic_version"}

MARKER_TABLE = "legacy_import"


class LegacyMigrationError(RuntimeError):
    """Aborts the migration with nothing dropped. Always carries the operator's next step."""


@dataclass
class Report:
    action: str  # "noop" | "migrated" | "zombie"
    rows_copied: dict[str, int] = field(default_factory=dict)
    dropped: bool = False
    messages: list[str] = field(default_factory=list)


def _log(report: Report, message: str) -> None:
    report.messages.append(message)
    print(f"[legacy-migration] {message}", flush=True)


def _schema_exists(conn: psycopg.Connection, schema: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (schema,))
        return cur.fetchone() is not None


def _table_exists(conn: psycopg.Connection, schema: str, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
            (schema, table),
        )
        return cur.fetchone() is not None


def _columns(conn: psycopg.Connection, schema: str, table: str) -> list[str]:
    """Column names in ordinal order."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (schema, table),
        )
        return [row[0] for row in cur.fetchall()]


def _count(conn: psycopg.Connection, schema: str, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(
            sql.Identifier(schema), sql.Identifier(table)
        ))
        return cur.fetchone()[0]


def _relations(conn: psycopg.Connection, schema: str) -> list[tuple[str, str]]:
    """Every relation in the schema as (name, relkind). Indexes and TOAST tables are excluded -
    they follow their parent table and are not independently interesting."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT c.relname, c.relkind FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relkind NOT IN ('i', 't')",
            (schema,),
        )
        return [(row[0], row[1]) for row in cur.fetchall()]


def _marker_present(conn: psycopg.Connection, schema: str) -> bool:
    if not _table_exists(conn, schema, MARKER_TABLE):
        return False
    return _count(conn, schema, MARKER_TABLE) > 0


def _copy_table(
    source: psycopg.Connection,
    target: psycopg.Connection,
    *,
    source_schema: str,
    target_schema: str,
    table: str,
    columns: list[str],
) -> None:
    """Streams one table between two connections. Kept as a separate function so tests can patch
    it to simulate a partial copy and prove the verification step actually refuses to drop."""
    col_list = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
    # COPY (SELECT ...) rather than COPY table - it pins the column order to `columns` on the read
    # side, so both ends agree positionally. Binary COPY carries no column names: it is positional
    # and type-tagged, so an implicit order would silently mis-assign values if the two schemas
    # ever grew their columns in a different sequence (they did - user_id/skin_person_id arrived in
    # 0002, is_admin in 0003, and a dropped-column tombstone shifts attnum besides).
    read_sql = sql.SQL("COPY (SELECT {cols} FROM {schema}.{table}) TO STDOUT (FORMAT BINARY)").format(
        cols=col_list, schema=sql.Identifier(source_schema), table=sql.Identifier(table)
    )
    write_sql = sql.SQL("COPY {schema}.{table} ({cols}) FROM STDIN (FORMAT BINARY)").format(
        schema=sql.Identifier(target_schema), table=sql.Identifier(table), cols=col_list
    )
    with source.cursor() as src_cur, target.cursor() as dst_cur:
        with src_cur.copy(read_sql) as reader, dst_cur.copy(write_sql) as writer:
            for block in reader:
                writer.write(block)


def _copy_columns(
    source: psycopg.Connection,
    target: psycopg.Connection,
    *,
    source_schema: str,
    target_schema: str,
    table: str,
) -> list[str]:
    """Columns present in BOTH schemas, in the target's order.

    Not simply the target's columns: an install being upgraded sits at whatever Alembic revision it
    last ran, which may predate columns the target now has (is_admin arrived in 0003). Those are
    nullable or defaulted precisely because a migration added them to a populated table, so letting
    the target fill them is exactly what running that migration would have done.
    """
    source_columns = set(_columns(source, source_schema, table))
    return [c for c in _columns(target, target_schema, table) if c in source_columns]


def migrate_legacy_schema(
    *,
    source_url: str,
    target_url: str,
    source_database: str,
    source_schema: str = "minigames",
    target_schema: str = "minigames",
) -> Report:
    """Copies the legacy schema's data into the target database and drops it from the source.

    `source_url` must be an admin connection to Immich's database (dropping the schema requires
    owning it, and the app role does not). `target_url` should be the app role's connection to its
    own database, so the copy runs as the owner of the tables Alembic just created.
    """
    report = Report(action="noop")

    with psycopg.connect(source_url) as source, psycopg.connect(target_url) as target:
        if not _schema_exists(source, source_schema):
            _log(report, f"no `{source_schema}` schema in `{source_database}` - nothing to do.")
            return report

        marker = _marker_present(target, target_schema)
        target_counts = {
            table: _count(target, target_schema, table)
            for table in LEGACY_TABLES
            if _table_exists(target, target_schema, table)
        }
        target_has_data = any(count > 0 for count in target_counts.values())

        if marker:
            # Zombie: this migration already committed once, and the legacy schema came back -
            # almost certainly an older Immich backup being restored after migrating. The app has
            # not written to it since (different database, and the role is read-only there), so
            # whatever it holds is stale by definition. Drop it without re-importing.
            report.action = "zombie"
            _log(
                report,
                f"`{source_schema}` reappeared in `{source_database}` after a completed migration "
                "(an Immich backup restored post-migration?). Its rows are stale and will NOT be "
                "re-imported.",
            )
        elif target_has_data:
            # Cannot tell "half-finished migration" from "install that wrote its own data" without
            # the marker. Either guess can destroy data, so refuse and make a human decide.
            nonempty = {t: c for t, c in target_counts.items() if c > 0}
            source_counts = {
                table: _count(source, source_schema, table)
                for table in LEGACY_TABLES
                if _table_exists(source, source_schema, table)
            }
            raise LegacyMigrationError(
                f"Refusing to migrate: the legacy schema `{source_schema}` still exists in "
                f"`{source_database}`, but the target database already holds data and carries no "
                f"completed-migration marker.\n"
                f"  target rows: {nonempty}\n"
                f"  legacy rows: {source_counts}\n"
                "Importing would risk duplicating or overwriting live data, so nothing was "
                "changed. Resolve by hand: keep whichever copy is authoritative, then either drop "
                f"the legacy schema (`DROP SCHEMA {source_schema} CASCADE` on `{source_database}`, "
                "as the admin role) or empty the target database, and re-run db-init."
            )
        else:
            report.action = "migrated"
            _copy_legacy_data(
                source,
                target,
                report=report,
                source_schema=source_schema,
                target_schema=target_schema,
                source_database=source_database,
            )

        _drop_legacy_schema(
            source, report=report, schema=source_schema, database=source_database
        )

    return report


def _copy_legacy_data(
    source: psycopg.Connection,
    target: psycopg.Connection,
    *,
    report: Report,
    source_schema: str,
    target_schema: str,
    source_database: str,
) -> None:
    """Copies every legacy table into one target transaction, verifies row counts inside it, and
    only then commits. Any mismatch or error rolls the target back, leaving the source untouched
    and the caller free to abort before anything is dropped."""
    # One snapshot for the whole read side: without it, a concurrent writer could change a table
    # between its COUNT and its COPY and the verification below would be comparing two different
    # states of the world - i.e. meaningless. The rollback first is required, not defensive:
    # psycopg refuses to change these attributes while a transaction is open, and the detection
    # queries in the caller have already opened one.
    source.rollback()
    source.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    source.read_only = True

    source_counts = {
        table: _count(source, source_schema, table)
        for table in LEGACY_TABLES
        if _table_exists(source, source_schema, table)
    }
    _log(report, f"legacy rows to copy: {source_counts}")

    try:
        for table in LEGACY_TABLES:
            if table not in source_counts:
                # An install that never ran the migration adding this table.
                _log(report, f"`{table}` absent from the legacy schema - skipped.")
                continue
            columns = _copy_columns(
                source,
                target,
                source_schema=source_schema,
                target_schema=target_schema,
                table=table,
            )
            _copy_table(
                source,
                target,
                source_schema=source_schema,
                target_schema=target_schema,
                table=table,
                columns=columns,
            )

        # Verified inside the still-open target transaction, so a mismatch rolls back the copy.
        copied = {table: _count(target, target_schema, table) for table in source_counts}
        mismatched = {
            table: (source_counts[table], copied[table])
            for table in source_counts
            if source_counts[table] != copied[table]
        }
        if mismatched:
            raise LegacyMigrationError(
                "Refusing to migrate: row counts do not match after copying "
                f"(table: expected, got) {mismatched}. The copy has been rolled back and the "
                "legacy schema left untouched - nothing was lost. Re-run db-init to retry."
            )

        with target.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "INSERT INTO {}.{} (id, source_database, rows_copied) VALUES (%s, %s, %s)"
                ).format(sql.Identifier(target_schema), sql.Identifier(MARKER_TABLE)),
                (uuid4(), source_database, Jsonb(copied)),
            )
        target.commit()
    except Exception:
        target.rollback()
        raise

    report.rows_copied = copied
    _log(report, f"copied and verified: {copied}")

    # The snapshot above cannot see writes committed after it began - and on `docker compose up -d`
    # the OLD backend container may still have been serving requests when the copy started. Ending
    # the snapshot and re-counting turns any such write into a loud failure with BOTH copies still
    # intact, instead of silent data loss at the drop below. (bootstrap_db_role.py sets the app
    # role read-only in this database before calling us, which closes that window; this is the
    # backstop for connections it had already opened.)
    source.rollback()
    recounted = {table: _count(source, source_schema, table) for table in source_counts}
    drifted = {
        table: (count, recounted[table])
        for table, count in source_counts.items()
        if recounted[table] != count
    }
    if drifted:
        raise LegacyMigrationError(
            f"Refusing to drop `{source_schema}`: it changed while being copied "
            f"(table: copied, now) {drifted} - most likely an older backend container still "
            "running and writing. The copy DID commit to the new database, and the legacy schema "
            "is untouched, so nothing is lost. Stop the old backend, then re-run db-init: it will "
            "see the completed-migration marker and clean up without re-importing."
        )


def _drop_legacy_schema(
    source: psycopg.Connection, *, report: Report, schema: str, database: str
) -> None:
    relations = _relations(source, schema)
    unexpected = [
        (name, kind) for name, kind in relations if kind != "r" or name not in KNOWN_LEGACY_TABLES
    ]
    if unexpected:
        raise LegacyMigrationError(
            f"Refusing to drop `{schema}` from `{database}`: it contains objects this migration "
            f"does not recognise: {unexpected}. `DROP SCHEMA ... CASCADE` would take them too. "
            "Nothing was changed; the copied data is safe in the new database. Inspect those "
            "objects and remove them by hand, then re-run db-init."
        )

    # End the REPEATABLE READ snapshot and clear the read-only flag the copy set - both are
    # connection-level in psycopg and would otherwise reject the DDL below.
    source.rollback()
    source.read_only = False
    source.isolation_level = None
    with source.cursor() as cur:
        cur.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
    source.commit()
    report.dropped = True
    _log(report, f"dropped schema `{schema}` from `{database}` - it is now out of Immich's backups.")


def main() -> None:  # pragma: no cover - thin CLI wrapper, exercised via bootstrap_db_role.py
    print(
        "Run this through scripts/bootstrap_db_role.py, which holds the admin credentials and "
        "provisions the target database first.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
