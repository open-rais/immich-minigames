"""
SQLAlchemy Core Table() declarations for the subset of Immich's own Postgres schema that the
games need to read. These mirror tables Immich owns and migrates (not this app's tables, see
games.py) - only the columns actually used are declared, not the full schema.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ENUM

metadata = MetaData()

# Native Postgres enum types (not plain varchar) - must be declared as such, otherwise comparing
# them against a string bind parameter fails with "operator does not exist: assets_status_enum =
# character varying". create_type=False because these enums are owned/migrated by Immich.
asset_status_enum = ENUM("active", "trashed", "deleted", name="assets_status_enum", create_type=False)
asset_visibility_enum = ENUM("archive", "timeline", "hidden", "locked", name="asset_visibility_enum", create_type=False)

asset = Table(
    "asset",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("ownerId", Uuid),
    Column("type", String),
    Column("fileCreatedAt", DateTime(timezone=True)),
    # Immich stores the device-local wall-clock time here as a timestamptz whose UTC rendering is
    # the local time (e.g. a 21:55 local shot is stored as 21:55+00), so casting it to date at UTC
    # recovers the true local calendar day - see immich_service.get_assets. Distinct from
    # fileCreatedAt, whose UTC day can differ. Used by Dateguessr/Timeline.
    Column("localDateTime", DateTime(timezone=True)),
    Column("originalFileName", String),
    Column("stackId", Uuid),
    Column("visibility", asset_visibility_enum),
    Column("status", asset_status_enum),
    Column("isFavorite", Boolean),
    Column("width", Integer),
    Column("height", Integer),
    Column("deletedAt", DateTime(timezone=True)),
)

asset_exif = Table(
    "asset_exif",
    metadata,
    Column("assetId", Uuid, primary_key=True),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("city", String),
    Column("state", String),
    Column("country", String),
)

asset_file = Table(
    "asset_file",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("assetId", Uuid),
    Column("type", String),
)

# Since Immich v3.2 a person is a `person_group` (its id is the public person id - the one the REST
# API, `/people/{id}` links and this app's own stored ids all use, carried over unchanged from the
# old `person.id`), and `person` holds one row *per Immich user who sees that person*, keyed by
# (ownerId, personGroupId), each with its own name/birthDate/isHidden. Several rows can therefore
# share a personGroupId once people are shared between users (v3.3) - see
# docs/ARCHITECTURE/IMMICH.md for how the queries pick one row per group.
person = Table(
    "person",
    metadata,
    Column("ownerId", Uuid, primary_key=True),
    Column("personGroupId", Uuid, primary_key=True),
    Column("name", String),
    Column("birthDate", Date),
    Column("thumbnailPath", String),
    Column("isHidden", Boolean),
)

album = Table(
    "album",
    metadata,
    Column("id", Uuid, primary_key=True),
    # No ownerId: Immich v3.0 dropped album."ownerId" in favor of an 'owner' row in album_user.
    Column("albumName", String),
    # The album's chosen cover asset (nullable - Immich falls back to the first asset). Used by
    # MoreOrLess's albumAssets mode to serve an album thumbnail - see immich_service.get_albums.
    Column("albumThumbnailAssetId", Uuid),
    Column("deletedAt", DateTime(timezone=True)),
)

# Join table between album and asset (Immich's own naming: albumId / assetId).
album_asset = Table(
    "album_asset",
    metadata,
    Column("albumId", Uuid, primary_key=True),
    Column("assetId", Uuid, primary_key=True),
)

asset_face = Table(
    "asset_face",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("assetId", Uuid),
    # Points at person_group.id (Immich v3.2+, formerly `personId` -> person.id), not at a `person`
    # row - see the note on `person` above.
    Column("personGroupId", Uuid),
    Column("isVisible", Boolean),
    Column("deletedAt", DateTime(timezone=True)),
    # Copied from the face's asset by Immich's own triggers (v3.3+), so face queries can filter on
    # the asset's owner/visibility/soft-delete without joining `asset`.
    Column("ownerId", Uuid),
    Column("assetVisibility", asset_visibility_enum),
    Column("assetDeletedAt", DateTime(timezone=True)),
    # Resolution the face detection was computed on (not necessarily the asset's own resolution -
    # the bounding box below must be scaled proportionally against whichever resolution it's drawn
    # on) and the box itself. Used by Who'sThatPerson to black out faces - see
    # docs/ARCHITECTURE/IMMICH.md's asset_face section.
    Column("imageWidth", Integer),
    Column("imageHeight", Integer),
    Column("boundingBoxX1", Integer),
    Column("boundingBoxY1", Integer),
    Column("boundingBoxX2", Integer),
    Column("boundingBoxY2", Integer),
)

# Immich's own accounts (not this app's - see persistence/users.py). Read only to rank which
# `person` row represents a person_group: the Immich admin's row first, then the oldest account's.
user = Table(
    "user",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("isAdmin", Boolean),
    Column("createdAt", DateTime(timezone=True)),
)

# One row per Immich version this database has run, written by Immich's microservices worker on
# startup - *after* its migrations, so for a few seconds after an upgrade the newest row can lag
# behind the schema. Only used to make the startup compatibility error readable; the check itself
# relies on the schema, not on this table.
version_history = Table(
    "version_history",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("version", String),
    Column("createdAt", DateTime(timezone=True)),
)
