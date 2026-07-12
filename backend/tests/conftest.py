"""
These are integration tests against the real dev Immich Postgres brought up by
docker-compose.yml (see docs/ARCHITECTURE/IMMICH.md) - it's seeded with real test data
specifically to exercise these queries. Run `docker compose up -d` first.
"""

import pytest

from persistance.immich_tables import get_engine
from services.immich_service import ImmichService


@pytest.fixture(scope="session")
def engine():
    return get_engine()


@pytest.fixture
def immich_service(engine):
    return ImmichService(engine)
