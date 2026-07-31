"""Per-request contextvars: the raw context_fields()
snapshot, and that logging_setup's formatters merge it into every record - not just ones an app
call site explicitly passes as `extra`. Same direct-formatter style as test_logging_setup.py,
no dictConfig/global logging state touched here."""

import io
import json
import logging

from api.request_context import context_fields, forwarded_for_var, ip_var, request_id_var, user_var
from logging_setup import ConsoleFormatter, JsonFormatter


def test_context_fields_empty_when_nothing_bound():
    assert context_fields() == {}


def test_context_fields_includes_only_what_is_set():
    token = request_id_var.set("req-1")
    try:
        assert context_fields() == {"request_id": "req-1"}
    finally:
        request_id_var.reset(token)


def test_context_fields_expands_user_into_id_and_username():
    token = user_var.set({"id": "u1", "username": "alice"})
    try:
        fields = context_fields()
        assert fields == {"user_id": "u1", "username": "alice"}
    finally:
        user_var.reset(token)


def _emit(formatter: logging.Formatter) -> str:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    logger = logging.getLogger(f"test.{id(stream)}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)
    try:
        logger.info("hello")
    finally:
        logger.removeHandler(handler)
    return stream.getvalue().strip()


def test_json_formatter_merges_bound_context_into_every_record():
    tokens = (
        request_id_var.set("req-2"),
        ip_var.set("127.0.0.1"),
        forwarded_for_var.set("1.2.3.4"),
    )
    try:
        payload = json.loads(_emit(JsonFormatter()))
    finally:
        for var, token in zip((request_id_var, ip_var, forwarded_for_var), tokens, strict=True):
            var.reset(token)

    assert payload["request_id"] == "req-2"
    assert payload["ip"] == "127.0.0.1"
    assert payload["forwarded_for"] == "1.2.3.4"


def test_console_formatter_merges_bound_context_into_every_record():
    token = request_id_var.set("req-3")
    try:
        line = _emit(ConsoleFormatter())
    finally:
        request_id_var.reset(token)

    assert "request_id=req-3" in line
