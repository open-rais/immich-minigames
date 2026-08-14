"""Ad-hoc timing diagnostics (roadmap #15 F0, see docs/TODO/ADMIN-WORKERS.md §4) - deliberately NOT
the `audit`/`access` loggers (docs/ARCHITECTURE/BACKEND.md §Logging): `timed()` logs through
ordinary `getLogger(__name__)` app logging, gated by `LOG_LEVEL` like everything else in that third
bucket, so it stays silent in production unless explicitly turned on."""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

_logger = logging.getLogger(__name__)


@contextmanager
def timed(event: str, *, level: int = logging.DEBUG, **fields: object) -> Iterator[None]:
    """Times the wrapped block and emits one log line shaped like audit.py's `audit()` (an `event`
    field plus whatever scalar fields the call site knows, formatted by logging_setup.py's
    formatters) with an added `ms` field. Pass `level=logging.INFO` for events worth seeing without
    opting into full DEBUG noise (see MLService's recompute-only logging)."""
    start = time.perf_counter()
    try:
        yield
    finally:
        ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.log(level, "", extra={"event": event, "ms": ms, **fields})
