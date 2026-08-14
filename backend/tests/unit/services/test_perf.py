"""perf.timed() unit tests - pure, no database. Unlike audit/access (logging_setup.py sets
propagate=False on those), `perf` is an ordinary getLogger(__name__) logger, so caplog's
root-attached handler sees it directly."""

import logging

import pytest

from perf import timed


def test_timed_emits_event_and_ms_at_debug_by_default(caplog):
    with caplog.at_level(logging.DEBUG, logger="perf"):
        with timed("some_query", foo="bar"):
            pass

    [record] = caplog.records
    assert record.levelno == logging.DEBUG
    assert record.event == "some_query"
    assert record.foo == "bar"
    assert isinstance(record.ms, float)
    assert record.ms >= 0


def test_timed_respects_explicit_level(caplog):
    with caplog.at_level(logging.INFO, logger="perf"):
        with timed("recompute", level=logging.INFO, entity="person"):
            pass

    [record] = caplog.records
    assert record.levelno == logging.INFO
    assert record.entity == "person"


def test_timed_still_logs_when_block_raises(caplog):
    with caplog.at_level(logging.DEBUG, logger="perf"):
        with pytest.raises(ValueError):
            with timed("boom"):
                raise ValueError("nope")

    [record] = caplog.records
    assert record.event == "boom"


def test_timed_not_emitted_below_configured_level(caplog):
    with caplog.at_level(logging.INFO, logger="perf"):
        with timed("noisy"):  # DEBUG default, logger only accepting INFO+
            pass

    assert caplog.records == []
