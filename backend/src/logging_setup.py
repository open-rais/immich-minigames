"""Structured logging (docs/TODO/LOGGING.md) - not `logging.py`: `src/` is on `sys.path`
(`--app-dir src`), so a module with that name would shadow the stdlib package."""

import json
import logging
import logging.config
from datetime import UTC, datetime

from config import Settings

_STANDARD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
    "message",
    "asctime",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
            + "Z",
            "level": record.levelname,
            "logger": record.name,
        }
        if "event" in record.__dict__:
            payload["event"] = record.__dict__["event"]
        else:
            payload["msg"] = record.getMessage()
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key != "event":
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        event_or_msg = record.__dict__.get("event", record.getMessage())
        line = f"{ts} {record.levelname:<8} {record.name} {event_or_msg}"
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_ATTRS and key != "event"
        }
        if extras:
            line += " " + " ".join(f"{key}={value}" for key, value in extras.items())
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def configure_logging(settings: Settings) -> None:
    formatter = "json" if settings.log_format == "json" else "console"
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "console": {"()": ConsoleFormatter},
                "json": {"()": JsonFormatter},
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter,
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": settings.log_level,
                "handlers": ["default"],
            },
            "loggers": {
                # Re-declared explicitly (not just left to inherit root) because uvicorn's own
                # Config.__init__ already attached its own handlers to these before this runs -
                # `handlers: []` is what clears them, `propagate: True` is what routes them
                # through our single stdout handler instead.
                "uvicorn": {"handlers": [], "propagate": True},
                "uvicorn.error": {"handlers": [], "propagate": True},
                # Replaced by the access-log middleware (docs/TODO/LOGGING.md §4.3, not built
                # yet) - silenced rather than left in its default per-request-line format.
                "uvicorn.access": {"handlers": [], "propagate": False},
                # Never filtered by LOG_LEVEL (decision [H]) - security/access events stay
                # visible even when LOG_LEVEL=ERROR silences app noise.
                "audit": {"handlers": ["default"], "level": "INFO", "propagate": False},
                "access": {"handlers": ["default"], "level": "INFO", "propagate": False},
            },
        }
    )
