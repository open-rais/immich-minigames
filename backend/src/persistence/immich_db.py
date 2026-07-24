"""
Connection to Immich's own database - read-only, and a different database from this app's own
(see base.py). Kept in its own module so that neither side's plumbing has to know about the other:
services/immich_service.py reads through immich_tables.py's Core `Table()` declarations, while
services/ml_service.py issues raw `text()` SQL and never imports those declarations at all, so a
neutral module is the honest home for both.

"Read-only" is enforced in Postgres, not here. scripts/bootstrap_db_role.py grants the app role
`pg_read_all_data` (SELECT, never INSERT/UPDATE/DELETE) on Immich's database, and additionally
sets `default_transaction_read_only` for the role in that database. The former is a hard
privilege boundary; the latter is a guard rail against programming mistakes, since the role can
still `SET TRANSACTION READ WRITE` on itself.
"""

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from config import get_settings


@lru_cache(maxsize=1)
def get_immich_engine() -> Engine:
    return create_engine(get_settings().immich_db_url, pool_pre_ping=True)
