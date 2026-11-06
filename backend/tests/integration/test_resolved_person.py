"""services/immich/_resolved_person.py's ranking of several `person` rows per person_group.

The dev Immich instance has a single user (exactly one row per group), so the multi-row cases can't
be exercised against its real data. Instead each test shadows Immich's `person`/`user` tables with
TEMP tables of the same names in this app's own database: Postgres resolves unqualified names
against pg_temp first, so the real compiled query runs against controlled rows, and nothing touches
Immich's database (which this app's role can't write to anyway).
"""

from uuid import UUID

import pytest
from sqlalchemy import select, text

from services.immich._resolved_person import resolved_person

ADMIN = UUID(int=1)  # created after OLDEST, so "admin first" isn't just "oldest first"
OLDEST = UUID(int=2)
NEWEST = UUID(int=3)


@pytest.fixture
def conn(app_engine):
    with app_engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(
            text('CREATE TEMP TABLE "user" (id uuid, "isAdmin" bool, "createdAt" timestamptz) ON COMMIT DROP')
        )
        connection.execute(
            text(
                'CREATE TEMP TABLE person ("ownerId" uuid, "personGroupId" uuid, name text, "birthDate" date, '
                '"thumbnailPath" text, "isHidden" bool) ON COMMIT DROP'
            )
        )
        connection.execute(
            text('INSERT INTO "user" VALUES (:admin, true, :t2), (:oldest, false, :t1), (:newest, false, :t3)'),
            {
                "admin": ADMIN,
                "oldest": OLDEST,
                "newest": NEWEST,
                "t1": "2020-01-01",
                "t2": "2024-01-01",
                "t3": "2025-01-01",
            },
        )
        yield connection
        transaction.rollback()


def _insert(conn, group: int, owner: UUID, name: str, *, birth=None, thumb: str = "", hidden: bool = False) -> UUID:
    group_id = UUID(int=100 + group)
    conn.execute(
        text("INSERT INTO person VALUES (:owner, :group_id, :name, :birth, :thumb, :hidden)"),
        {"owner": owner, "group_id": group_id, "name": name, "birth": birth, "thumb": thumb, "hidden": hidden},
    )
    return group_id


def _resolve(conn, group_id: UUID):
    rows = conn.execute(select(resolved_person).where(resolved_person.c.id == group_id)).all()
    assert len(rows) == 1, "exactly one resolved row per person_group"
    return rows[0]


def test_admin_name_wins_when_the_admin_has_one(conn):
    group = _insert(conn, 1, ADMIN, "Ana")
    _insert(conn, 1, OLDEST, "Anita")

    assert _resolve(conn, group).name == "Ana"


def test_another_users_name_is_used_when_the_admins_row_is_unnamed(conn):
    group = _insert(conn, 1, ADMIN, "")
    _insert(conn, 1, NEWEST, "Beto")

    assert _resolve(conn, group).name == "Beto"


def test_admin_row_is_used_when_nobody_named_the_person(conn):
    group = _insert(conn, 1, ADMIN, "", hidden=True)
    _insert(conn, 1, OLDEST, "")

    resolved = _resolve(conn, group)
    assert resolved.name == ""
    assert resolved.isHidden is True


def test_oldest_account_breaks_the_tie_without_an_admin_row(conn):
    group = _insert(conn, 1, NEWEST, "Caro-new")
    _insert(conn, 1, OLDEST, "Caro-old")

    assert _resolve(conn, group).name == "Caro-old"


def test_hidden_flag_comes_from_the_winning_row(conn):
    group = _insert(conn, 1, ADMIN, "Ana", hidden=False)
    _insert(conn, 1, OLDEST, "Anita", hidden=True)

    assert _resolve(conn, group).isHidden is False


def test_birth_date_falls_back_to_the_next_ranked_row_that_has_one(conn):
    group = _insert(conn, 1, ADMIN, "Ana")
    _insert(conn, 1, NEWEST, "Anita", birth="1995-03-03")
    _insert(conn, 1, OLDEST, "Ani", birth="1990-05-01")

    # Ana (admin) has none; of the rest, OLDEST ranks above NEWEST.
    assert str(_resolve(conn, group).birthDate) == "1990-05-01"


def test_has_thumbnail_when_any_row_in_the_group_has_one(conn):
    with_crop = _insert(conn, 1, ADMIN, "Ana")
    _insert(conn, 1, OLDEST, "Anita", thumb="/thumbs/anita.jpeg")
    without_crop = _insert(conn, 2, ADMIN, "Beto")

    assert _resolve(conn, with_crop).hasThumbnail is True
    assert _resolve(conn, without_crop).hasThumbnail is False
