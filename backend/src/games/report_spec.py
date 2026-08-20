"""Contract-only module (no logic) - the shared vocabulary for the metadata-reporting feature: what
an entity/reason pair can be, and which reason applies to which entity type. Lives in games/ (not
services/) for the same reason games/settings_spec.py does - a future per-game reports.py can
declare which reasons exclude it from round generation without games/ depending on services/."""

from enum import StrEnum


class ReportEntity(StrEnum):
    ASSET = "asset"
    PERSON = "person"
    ALBUM = "album"


class ReportReason(StrEnum):
    PERSON_BIRTH_DATE = "person_birth_date"
    PERSON_NAME_FACE_MISMATCH = "person_name_face_mismatch"
    PERSON_NAME_SPELLING = "person_name_spelling"
    ALBUM_COVER_MISMATCH = "album_cover_mismatch"
    ALBUM_NAME_SPELLING = "album_name_spelling"
    ASSET_LOCATION = "asset_location"
    ASSET_DATE = "asset_date"
    ASSET_FACE_MISMATCH = "asset_face_mismatch"


# Explicit, not parsed from the reason's name prefix - a reason renamed later shouldn't silently
# change which entity it applies to.
REASON_ENTITY: dict[ReportReason, ReportEntity] = {
    ReportReason.PERSON_BIRTH_DATE: ReportEntity.PERSON,
    ReportReason.PERSON_NAME_FACE_MISMATCH: ReportEntity.PERSON,
    ReportReason.PERSON_NAME_SPELLING: ReportEntity.PERSON,
    ReportReason.ALBUM_COVER_MISMATCH: ReportEntity.ALBUM,
    ReportReason.ALBUM_NAME_SPELLING: ReportEntity.ALBUM,
    ReportReason.ASSET_LOCATION: ReportEntity.ASSET,
    ReportReason.ASSET_DATE: ReportEntity.ASSET,
    ReportReason.ASSET_FACE_MISMATCH: ReportEntity.ASSET,
}
