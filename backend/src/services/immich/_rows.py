"""Row -> domain object mappers, shared by assets.py/persons.py/albums.py/faces.py."""

from sqlalchemy.engine import Row

from domain.album import Album
from domain.asset import Asset
from domain.face import Face
from domain.person import Person


def row_to_asset(row: Row) -> Asset:
    return Asset(
        id=row.id,
        type=row.type,
        file_created_at=row.fileCreatedAt,
        local_date=row.localDate,
        original_file_name=row.originalFileName,
        width=row.width,
        height=row.height,
        is_favorite=row.isFavorite,
        latitude=row.latitude,
        longitude=row.longitude,
        city=row.city,
        state=row.state,
        country=row.country,
    )


def row_to_album(row: Row) -> Album:
    return Album(
        id=row.id,
        name=row.albumName,
        asset_count=row.asset_count,
        thumbnail_asset_id=row.albumThumbnailAssetId,
    )


def row_to_person(row: Row) -> Person:
    return Person(
        id=row.id,
        name=row.name,
        birth_date=row.birthDate,
        asset_count=row.asset_count,
    )


def row_to_face(row: Row) -> Face:
    return Face(
        id=row.id,
        asset_id=row.assetId,
        person_id=row.personId,
        person_name=row.name,
        image_width=row.imageWidth,
        image_height=row.imageHeight,
        bounding_box_x1=row.boundingBoxX1,
        bounding_box_y1=row.boundingBoxY1,
        bounding_box_x2=row.boundingBoxX2,
        bounding_box_y2=row.boundingBoxY2,
    )
