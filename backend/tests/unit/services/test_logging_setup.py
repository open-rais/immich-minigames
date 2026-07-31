"""Unit tests against the formatters directly - no
dictConfig, no touching global logging state (that wiring is verified live separately,
not here - see the module's own docstring risk notes about pytest/caplog interaction)."""

import io
import json
import logging

from logging_setup import ConsoleFormatter, JsonFormatter


def _record_line(formatter: logging.Formatter, log_fn_name: str, msg: str, **extra) -> str:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    logger = logging.getLogger(f"test.{id(stream)}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)
    try:
        getattr(logger, log_fn_name)(msg, extra=extra)
    finally:
        logger.removeHandler(handler)
    return stream.getvalue().strip()


def test_json_formatter_emits_valid_json_line_with_extras():
    line = _record_line(JsonFormatter(), "info", "hello", foo="bar")

    assert "\n" not in line
    payload = json.loads(line)
    assert payload["ts"].endswith("Z")
    assert payload["level"] == "INFO"
    assert payload["logger"].startswith("test.")
    assert payload["msg"] == "hello"
    assert payload["foo"] == "bar"
    assert "event" not in payload


def test_json_formatter_uses_event_field_for_audit_style_extra():
    line = _record_line(JsonFormatter(), "info", "", event="login_failed", email="x@example.com")

    payload = json.loads(line)
    assert payload["event"] == "login_failed"
    assert payload["email"] == "x@example.com"
    assert "msg" not in payload


def test_json_formatter_serializes_exception_as_single_line_field():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(f"test.{id(stream)}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)
    try:
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("failed")
    finally:
        logger.removeHandler(handler)

    line = stream.getvalue().strip()
    assert len(line.splitlines()) == 1
    payload = json.loads(line)
    assert "Traceback" in payload["exc"]
    assert "ValueError: boom" in payload["exc"]


def test_console_formatter_is_readable_with_k_v_extras():
    line = _record_line(ConsoleFormatter(), "info", "hello", foo="bar")

    assert "hello" in line
    assert "foo=bar" in line
