"""Tests for scripts/migrate_legacy_schema.py - the one-time move of this app's tables out of a
`minigames` schema inside Immich's database and into this app's own database.

This is the only destructive code in the repo (it ends in `DROP SCHEMA ... CASCADE`), so it gets
real coverage rather than a smoke test. Every test runs against two throwaway databases created and
dropped per test - Immich's real database is never touched, and neither is the app's own.

The "legacy" source database is built by running Alembic up to 0004, the revision that was head
before the split, so these tests exercise the actual historical schema rather than a hand-rolled
approximation of it.
"""

import uuid
from datetime import datetime
from pathlib import Path

import psycopg
import pytest
from dotenv import dotenv_values
from psycopg import sql
from psycopg.types.json import Jsonb

from scripts.migrate_legacy_schema import (
    LegacyMigrationError,
    migrate_legacy_schema,
)

_ENV = {
    **dotenv_values(Path(__file__).resolve().parents[2] / ".env"),
}

_ADMIN_USER = _ENV.get("DB_USERNAME")
_ADMIN_PASSWORD = _ENV.get("DB_PASSWORD")
_HOST = _ENV.get("DB_HOST", "localhost")
_PORT = _ENV.get("DB_PORT", "5432")

pytestmark = pytest.mark.skipif(
    not (_ADMIN_USER and _ADMIN_PASSWORD),
    reason="needs Immich's admin DB credentials (DB_USERNAME/DB_PASSWORD) to create test databases",
)

LEGACY_SCHEMA = "minigames"


def _admin_url(database: str) -> str:
    return f"postgresql://{_ADMIN_USER}:{_ADMIN_PASSWORD}@{_HOST}:{_PORT}/{database}"


def _run_alembic(database: str, revision: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option(
        "sqlalchemy.url", _admin_url(database).replace("postgresql://", "postgresql+psycopg://")
    )
    command.upgrade(cfg, revision)


def _create_database(name: str) -> None:
    with psycopg.connect(_admin_url("postgres"), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def _drop_database(name: str) -> None:
    with psycopg.connect(_admin_url("postgres"), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (name,)
        )
        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))


def _create_legacy_schema(database: str, *, revision: str = "0004") -> None:
    """Builds the pre-split schema: bootstrap_db_role.py created the schema, Alembic filled it."""
    with psycopg.connect(_admin_url(database), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(LEGACY_SCHEMA)))
    _run_alembic(database, revision)


@pytest.fixture
def databases():
    """Two throwaway databases: `source` stands in for Immich's, `target` for this app's own."""
    suffix = uuid.uuid4().hex[:12]
    source, target = f"mg_test_src_{suffix}", f"mg_test_dst_{suffix}"
    _create_database(source)
    _create_database(target)
    try:
        yield source, target
    finally:
        _drop_database(source)
        _drop_database(target)


@pytest.fixture
def migrated_target(databases):
    """Target database at head, i.e. what db-init leaves behind before the copy runs."""
    source, target = databases
    with psycopg.connect(_admin_url(target), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(LEGACY_SCHEMA)))
        # Mirrors scripts/bootstrap_db_role.py's _configure_app_database, which now installs this
        # before running migrations - head includes 0006's person_face_embedding_cache table,
        # whose `embedding` column needs the `vector` type to exist.
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _run_alembic(target, "head")
    return source, target


def _seed_legacy(database: str) -> dict[str, int]:
    """Writes a row set that covers the shapes most likely to survive a copy incorrectly:
    non-ASCII text, nested/unicode JSONB, sub-second timestamps, nullable FKs and nullable ints."""
    user_id = uuid.uuid4()
    anon_game_id, user_game_id = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(_admin_url(database)) as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {LEGACY_SCHEMA}.users "
            "(id, email, username, full_name, password_hash, skin_person_id, is_admin, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                user_id,
                "raúl@example.com",
                "raúl",
                "Raúl Rodríguez Ñandú",
                "$argon2id$fake",
                uuid.uuid4(),
                True,
                datetime(2026, 3, 4, 5, 6, 7, 891011),
            ),
        )
        # One anonymous game (user_id NULL) and one owned - the null FK is the case a naive
        # column-order bug would silently mangle.
        for game_id, owner_user in ((anon_game_id, None), (user_game_id, user_id)):
            cur.execute(
                f"INSERT INTO {LEGACY_SCHEMA}.games "
                "(id, owner, user_id, game_type, mode, score, finished, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    game_id,
                    "anon-owner-id",
                    owner_user,
                    "geoguessr",
                    "classic",
                    4200,
                    True,
                    datetime(2026, 3, 4, 5, 6, 7, 123456),
                ),
            )
        # score_delta NULL = an unanswered round; payload exercises nesting and non-ASCII keys.
        cur.execute(
            f"INSERT INTO {LEGACY_SCHEMA}.rounds "
            "(id, game_id, round_index, score_delta, payload, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                uuid.uuid4(),
                anon_game_id,
                0,
                None,
                Jsonb({"asset": {"lat": -33.45, "lon": -70.66}, "ciudad": "Santiago", "tags": []}),
                datetime(2026, 3, 4, 5, 6, 8, 654321),
            ),
        )
        cur.execute(
            f"INSERT INTO {LEGACY_SCHEMA}.rounds "
            "(id, game_id, round_index, score_delta, payload, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (uuid.uuid4(), user_game_id, 0, 850, Jsonb({"nested": {"deep": [1, 2, {"x": None}]}}), datetime.now()),
        )
        cur.execute(
            f"INSERT INTO {LEGACY_SCHEMA}.game_settings (game_type, values) VALUES (%s, %s)",
            ("immichdle", Jsonb({"max_guesses": 8})),
        )
        conn.commit()
    return {"users": 1, "games": 2, "rounds": 2, "game_settings": 1}


def _counts(database: str, schema: str = LEGACY_SCHEMA) -> dict[str, int]:
    tables = ("users", "games", "rounds", "game_settings")
    with psycopg.connect(_admin_url(database)) as conn, conn.cursor() as cur:
        result = {}
        for table in tables:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = %s AND table_name = %s",
                (schema, table),
            )
            if cur.fetchone() is None:
                continue
            cur.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(schema), sql.Identifier(table)
            ))
            result[table] = cur.fetchone()[0]
    return result


def _schema_exists(database: str, schema: str = LEGACY_SCHEMA) -> bool:
    with psycopg.connect(_admin_url(database)) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (schema,))
        return cur.fetchone() is not None


def _migrate(source: str, target: str):
    return migrate_legacy_schema(
        source_url=_admin_url(source),
        target_url=_admin_url(target),
        source_database=source,
    )


class TestFreshInstall:
    def test_no_legacy_schema_is_a_complete_noop(self, migrated_target):
        """The guarantee that matters most: a brand new install must not be touched at all."""
        source, target = migrated_target
        assert not _schema_exists(source)

        report = _migrate(source, target)

        assert report.action == "noop"
        assert report.rows_copied == {}
        assert report.dropped is False
        assert _counts(target) == {"users": 0, "games": 0, "rounds": 0, "game_settings": 0}
        assert not _schema_exists(source)


class TestHappyPath:
    def test_copies_every_row_and_drops_the_legacy_schema(self, migrated_target):
        source, target = migrated_target
        _create_legacy_schema(source)
        expected = _seed_legacy(source)

        report = _migrate(source, target)

        assert report.action == "migrated"
        assert report.rows_copied == expected
        assert report.dropped is True
        assert _counts(target) == expected
        assert not _schema_exists(source), "legacy schema must be gone from Immich's database"

    def test_preserves_values_exactly_not_just_row_counts(self, migrated_target):
        source, target = migrated_target
        _create_legacy_schema(source)
        _seed_legacy(source)

        _migrate(source, target)

        with psycopg.connect(_admin_url(target)) as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT email, username, full_name, is_admin, created_at FROM {LEGACY_SCHEMA}.users"
            )
            email, username, full_name, is_admin, created_at = cur.fetchone()
            assert (email, username, full_name) == ("raúl@example.com", "raúl", "Raúl Rodríguez Ñandú")
            assert is_admin is True
            assert created_at == datetime(2026, 3, 4, 5, 6, 7, 891011), "microseconds must survive"

            cur.execute(
                f"SELECT payload FROM {LEGACY_SCHEMA}.rounds WHERE score_delta IS NULL"
            )
            (payload,) = cur.fetchone()
            assert payload == {
                "asset": {"lat": -33.45, "lon": -70.66},
                "ciudad": "Santiago",
                "tags": [],
            }

            # The anonymous game's null FK, and the owned game's intact one.
            cur.execute(
                f"SELECT count(*) FROM {LEGACY_SCHEMA}.games g "
                f"JOIN {LEGACY_SCHEMA}.users u ON u.id = g.user_id"
            )
            assert cur.fetchone()[0] == 1
            cur.execute(f"SELECT count(*) FROM {LEGACY_SCHEMA}.games WHERE user_id IS NULL")
            assert cur.fetchone()[0] == 1

    def test_empty_legacy_schema_still_migrates_and_drops(self, migrated_target):
        """An install that was set up but never played. Zero rows is a successful migration, not
        'nothing to do' - the schema still has to leave Immich's database."""
        source, target = migrated_target
        _create_legacy_schema(source)

        report = _migrate(source, target)

        assert report.action == "migrated"
        assert report.rows_copied == {"users": 0, "games": 0, "rounds": 0, "game_settings": 0}
        assert report.dropped is True
        assert not _schema_exists(source)

    def test_copies_tables_in_foreign_key_order(self, migrated_target):
        """games.user_id references users.id, so users must land first or the copy fails."""
        source, target = migrated_target
        _create_legacy_schema(source)
        _seed_legacy(source)

        _migrate(source, target)  # would raise ForeignKeyViolation on a wrong order

        with psycopg.connect(_admin_url(target)) as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT count(*) FROM {LEGACY_SCHEMA}.games WHERE user_id IS NOT NULL "
                f"AND user_id NOT IN (SELECT id FROM {LEGACY_SCHEMA}.users)"
            )
            assert cur.fetchone()[0] == 0

    def test_older_install_missing_a_later_column_still_migrates(self, migrated_target):
        """An install that stopped at 0002 has no users.is_admin. The column is defaulted precisely
        because a migration added it to a populated table, so the target should fill it."""
        source, target = migrated_target
        _create_legacy_schema(source, revision="0002")
        with psycopg.connect(_admin_url(source)) as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {LEGACY_SCHEMA}.users "
                "(id, email, username, full_name, password_hash) VALUES (%s, %s, %s, %s, %s)",
                (uuid.uuid4(), "a@b.c", "someone", "Some One", "hash"),
            )
            conn.commit()

        report = _migrate(source, target)

        assert report.action == "migrated"
        assert report.rows_copied["users"] == 1
        # game_settings arrived in 0004 - absent from the source, so simply skipped.
        assert "game_settings" not in report.rows_copied
        with psycopg.connect(_admin_url(target)) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT is_admin FROM {LEGACY_SCHEMA}.users")
            assert cur.fetchone()[0] is False


class TestRefusesToDestroy:
    def test_count_mismatch_rolls_back_and_drops_nothing(self, migrated_target, monkeypatch):
        source, target = migrated_target
        _create_legacy_schema(source)
        expected = _seed_legacy(source)

        import scripts.migrate_legacy_schema as module

        real_copy = module._copy_table

        def partial_copy(*args, table: str, **kwargs):
            if table == "rounds":
                return  # simulate a copy that silently moves nothing
            return real_copy(*args, table=table, **kwargs)

        monkeypatch.setattr(module, "_copy_table", partial_copy)

        with pytest.raises(LegacyMigrationError, match="row counts do not match"):
            _migrate(source, target)

        assert _counts(source) == expected, "source must be untouched"
        assert _schema_exists(source), "nothing may be dropped after a failed verification"
        assert _counts(target) == {"users": 0, "games": 0, "rounds": 0, "game_settings": 0}, (
            "the whole copy must roll back, not just the failing table"
        )

    def test_ambiguous_state_refuses_without_touching_anything(self, migrated_target):
        """Target already holds data but carries no marker: cannot tell a half-finished migration
        from an install that wrote its own data, and either guess can destroy something."""
        source, target = migrated_target
        _create_legacy_schema(source)
        expected = _seed_legacy(source)
        with psycopg.connect(_admin_url(target)) as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {LEGACY_SCHEMA}.users "
                "(id, email, username, full_name, password_hash) VALUES (%s, %s, %s, %s, %s)",
                (uuid.uuid4(), "live@example.com", "live", "Live User", "hash"),
            )
            conn.commit()

        with pytest.raises(LegacyMigrationError, match="no completed-migration marker"):
            _migrate(source, target)

        assert _counts(source) == expected
        assert _schema_exists(source)
        assert _counts(target)["users"] == 1, "existing target data must be left alone"

    def test_unrecognised_object_in_legacy_schema_blocks_the_drop(self, migrated_target):
        """DROP ... CASCADE is unbounded; an object we don't recognise means we don't know what
        we'd be deleting."""
        source, target = migrated_target
        _create_legacy_schema(source)
        _seed_legacy(source)
        with psycopg.connect(_admin_url(source), autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(f"CREATE TABLE {LEGACY_SCHEMA}.someone_elses_table (id int)")

        with pytest.raises(LegacyMigrationError, match="does not recognise"):
            _migrate(source, target)

        assert _schema_exists(source)

    def test_view_in_legacy_schema_blocks_the_drop(self, migrated_target):
        source, target = migrated_target
        _create_legacy_schema(source)
        _seed_legacy(source)
        with psycopg.connect(_admin_url(source), autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(f"CREATE VIEW {LEGACY_SCHEMA}.games_view AS SELECT * FROM {LEGACY_SCHEMA}.games")

        with pytest.raises(LegacyMigrationError, match="does not recognise"):
            _migrate(source, target)

        assert _schema_exists(source)


class TestRerun:
    def test_second_run_is_a_noop(self, migrated_target):
        source, target = migrated_target
        _create_legacy_schema(source)
        expected = _seed_legacy(source)
        _migrate(source, target)

        report = _migrate(source, target)

        assert report.action == "noop"
        assert _counts(target) == expected, "no duplicate import on re-run"

    def test_resurrected_legacy_schema_is_dropped_without_reimporting(self, migrated_target):
        """An Immich backup restored after migrating brings the old schema back. Its rows are stale
        by definition - the app has written only to the new database since."""
        source, target = migrated_target
        _create_legacy_schema(source)
        expected = _seed_legacy(source)
        _migrate(source, target)
        # The restore brings back the schema, rows and all.
        _create_legacy_schema(source)
        _seed_legacy(source)

        report = _migrate(source, target)

        assert report.action == "zombie"
        assert report.dropped is True
        assert _counts(target) == expected, "stale rows must not be re-imported or duplicated"
        assert not _schema_exists(source)
