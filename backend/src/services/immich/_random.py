"""Uniform random sampling over Immich's Postgres tables without `ORDER BY random()` (docs/TODO/
CODE-REVIEW-BACK.md B-1). `ORDER BY random()` forces Postgres to scan and sort every row matching
the query before returning the top `limit`, so its cost scales with the size of the whole matching
set instead of `limit` - invisible on a small dev library, a real cost at real-world scale (a
synthetic-data benchmark confirmed the query plan stays a full Seq Scan/Hash Join -> Sort at 20k
rows, while the pivot below stays flat, sub-3ms, at every scale tested from 1k to 20k).

Only worth applying where the sort is actually the bottleneck - `get_persons`/`get_albums` sort a
small already-aggregated result (one row per person/album), so their real cost lives in the join
that computes asset_count beforehand, which this doesn't touch. `get_assets` and
`get_random_asset_with_named_faces` sort the filtered set directly, so this is a real fix for both.
"""

from uuid import uuid4

from sqlalchemy import Column
from sqlalchemy.engine import Connection, Row
from sqlalchemy.sql import Select


def sample_by_id_pivot(conn: Connection, stmt: Select, id_column: Column, limit: int) -> list[Row]:
    """Picks a uniformly random pivot value and takes the next `limit` rows in `id_column` order
    from `stmt` (already filtered, not yet ordered/limited), wrapping around (id < pivot) if the
    tail after the pivot has fewer than `limit` rows - an index range scan instead of a full sort.

    Safe only when `id_column` is itself uniformly distributed and carries no real-world meaning -
    Immich's asset/asset_face ids are `uuid_generate_v4()` (random by construction), never the
    time-ordered `uuid_v7()` `updateId` column. Pivoting on a column that correlates with anything
    a player could notice (upload time, location) would bias which rows come back - see this
    module's docstring and docs/TODO/CODE-REVIEW-BACK.md B-1 for why that doesn't apply here."""
    if limit <= 0:
        return []
    pivot = uuid4()
    rows = list(conn.execute(stmt.where(id_column >= pivot).order_by(id_column).limit(limit)).all())
    if len(rows) < limit:
        rows += conn.execute(stmt.where(id_column < pivot).order_by(id_column).limit(limit - len(rows))).all()
    return rows
