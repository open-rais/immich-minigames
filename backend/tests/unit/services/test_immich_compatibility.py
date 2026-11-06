import logging

import pytest

from services.immich import compatibility
from services.immich.compatibility import (
    CompatibilityReport,
    ImmichIncompatibleError,
    check_compatibility,
    error_message,
    parse_version,
    required_columns,
)


def _patch_report(monkeypatch, report: CompatibilityReport) -> None:
    monkeypatch.setattr(compatibility, "inspect_compatibility", lambda _engine: report)


class TestParseVersion:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [("3.3.6", (3, 3, 6)), ("v3.4.0-rc.2", (3, 4, 0)), ("1.90.0", (1, 90, 0))],
    )
    def test_parses_plain_prefixed_and_prerelease_versions(self, value, expected):
        assert parse_version(value) == expected

    @pytest.mark.parametrize("value", [None, "", "release", "3.3"])
    def test_returns_none_for_anything_that_is_not_a_version(self, value):
        assert parse_version(value) is None


class TestRequiredColumns:
    def test_includes_the_v3_3_person_model_columns(self):
        assert {
            ("person", "personGroupId"),
            ("asset_face", "personGroupId"),
            ("asset_face", "ownerId"),
        } <= required_columns()

    def test_includes_columns_only_read_through_raw_sql(self):
        assert {("face_search", "embedding"), ("smart_search", "embedding")} <= required_columns()

    def test_no_longer_expects_the_pre_v3_2_person_columns(self):
        assert ("person", "id") not in required_columns()
        assert ("asset_face", "personId") not in required_columns()


class TestCheckCompatibility:
    def test_missing_columns_refuse_to_start_naming_the_version_and_columns(self, monkeypatch):
        _patch_report(
            monkeypatch,
            CompatibilityReport(
                missing_columns=frozenset({("person", "personGroupId"), ("asset_face", "ownerId")}),
                detected_version="3.0.3",
            ),
        )

        with pytest.raises(ImmichIncompatibleError) as error:
            check_compatibility(engine=None)

        message = str(error.value)
        assert "requires Immich v3.3.0 or newer" in message
        assert "detected: v3.0.3" in message
        assert "asset_face.ownerId, person.personGroupId" in message

    def test_missing_columns_still_refuse_when_the_version_claims_to_be_recent(self, monkeypatch):
        # The schema decides, not the recorded version.
        _patch_report(
            monkeypatch,
            CompatibilityReport(missing_columns=frozenset({("person", "personGroupId")}), detected_version="9.0.0"),
        )

        with pytest.raises(ImmichIncompatibleError):
            check_compatibility(engine=None)

    def test_schema_ok_but_lagging_version_only_warns(self, monkeypatch, caplog):
        # Right after an upgrade Immich's schema is already migrated but version_history still
        # names the previous version for a few seconds.
        _patch_report(monkeypatch, CompatibilityReport(missing_columns=frozenset(), detected_version="3.0.3"))

        with caplog.at_level(logging.WARNING, logger=compatibility.__name__):
            check_compatibility(engine=None)

        assert "v3.0.3" in caplog.text

    def test_schema_ok_and_supported_version_is_silent(self, monkeypatch, caplog):
        _patch_report(monkeypatch, CompatibilityReport(missing_columns=frozenset(), detected_version="3.3.6"))

        with caplog.at_level(logging.WARNING, logger=compatibility.__name__):
            check_compatibility(engine=None)

        assert caplog.text == ""


def test_error_message_without_a_recorded_version():
    report = CompatibilityReport(missing_columns=frozenset({("version_history", "version")}), detected_version=None)

    assert "detected: unknown version" in error_message(report)
