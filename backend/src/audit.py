"""Audit events - the single entry point for the `audit` logger (INFO, never filtered by
LOG_LEVEL, see logging_setup.py). Call sites pass a static event name and whatever scalar fields
are specific to that event; the actor/request context (user, request_id, ip...) is never passed
here - it's merged in later, at format time, from the contextvars in api/request_context.py."""

import logging

from logging_setup import RESERVED_LOG_RECORD_ATTRS

_logger = logging.getLogger("audit")


def audit(event: str, **fields: object) -> None:
    for key in fields:
        if key in RESERVED_LOG_RECORD_ATTRS:
            raise ValueError(f"audit() field {key!r} collides with a reserved LogRecord attribute")
    _logger.info("", extra={"event": event, **fields})
