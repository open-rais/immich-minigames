"""
SQLAlchemy Core Table() declarations for the subset of Immich's own Postgres schema that the
games need to read. These mirror tables Immich owns and migrates (not this app's tables, see
games.py) - only the columns actually used are declared, not the full schema.
"""

from functools import lru_cache

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
    create_engine,
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.engine import Engine

from config import Settings

metadata = MetaData()

# Native Postgres enum types (not plain varchar) - must be declared as such, otherwise comparing
# them against a string bind parameter fails with "operator does not exist: assets_status_enum =
# character varying". create_type=False because these enums are owned/migrated by Immich.
asset_status_enum = ENUM("active", "trashed", "deleted", name="assets_status_enum", create_type=False)
asset_visibility_enum = ENUM(
    "archive", "timeline", "hidden", "locked", name="asset_visibility_enum", create_type=False
)

asset = Table(
    "asset",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("ownerId", Uuid),
    Column("type", String),
    Column("fileCreatedAt", DateTime(timezone=True)),
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

person = Table(
    "person",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("ownerId", Uuid),
    Column("name", String),
    Column("birthDate", Date),
    Column("thumbnailPath", String),
    Column("isHidden", Boolean),
)

asset_face = Table(
    "asset_face",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("assetId", Uuid),
    Column("personId", Uuid),
    Column("isVisible", Boolean),
    Column("deletedAt", DateTime(timezone=True)),
)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(Settings().db_url)
