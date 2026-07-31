"""Postgres queries over Immich's `asset_face` table, joined with `person` for named faces."""

import random
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from domain.face import Face
from persistence.immich_tables import asset, asset_face, person

from ._rows import row_to_face


def get_random_asset_with_named_faces(
    engine: Engine, *, max_faces: int, exclude_asset_ids: frozenset[UUID] = frozenset()
) -> list[Face]:
    """Picks one random asset that has at least one visible, non-deleted face already assigned
    to a named, non-hidden person, then returns the faces Who'sThatPerson blacks out for a
    round: every one of that asset's named, non-hidden faces if it has `max_faces` or fewer,
    otherwise a *random* number of them between 1 and `max_faces` (confirmed with the project
    owner - not always exactly `max_faces`, so a photo with plenty of named people doesn't
    deterministically always hide the maximum). Faces without a name are never returned -
    there'd be nothing to grade against, so they're left unblacked in the photo, purely
    decorative. Hidden people (Immich's own `isHidden` flag) are excluded the same way
    get_persons/search_persons already exclude them from the guess search box - otherwise a
    round could black out a face the player has no way to search for and guess. Empty list if
    no eligible asset exists (e.g. exclude_asset_ids/the game's data pool is exhausted)."""
    visible_face = asset_face.c.isVisible.is_(True) & asset_face.c.deletedAt.is_(None)
    named_face = asset_face.join(person, person.c.id == asset_face.c.personId)

    asset_id_stmt = (
        select(asset.c.id)
        .select_from(asset.join(named_face, asset_face.c.assetId == asset.c.id))
        .where(
            asset.c.status == "active",
            asset.c.visibility == "timeline",
            asset.c.deletedAt.is_(None),
            visible_face,
            person.c.name != "",
            person.c.isHidden.is_(False),
        )
    )
    if exclude_asset_ids:
        asset_id_stmt = asset_id_stmt.where(asset.c.id.notin_(exclude_asset_ids))
    # GROUP BY (not DISTINCT) - Postgres rejects `SELECT DISTINCT ... ORDER BY random()`
    # (ORDER BY expressions must appear in the select list for DISTINCT), same reason
    # get_persons uses GROUP BY + ORDER BY random() instead of DISTINCT.
    asset_id_stmt = asset_id_stmt.group_by(asset.c.id).order_by(func.random()).limit(1)

    with engine.connect() as conn:
        asset_row = conn.execute(asset_id_stmt).first()
        if asset_row is None:
            return []

        # No SQL-level LIMIT here - every eligible face is fetched so the count to actually
        # hide can be decided in Python below (this asset's face count is at most a handful,
        # never a performance concern).
        faces_stmt = (
            select(
                asset_face.c.id,
                asset_face.c.assetId,
                asset_face.c.personId,
                person.c.name,
                asset_face.c.imageWidth,
                asset_face.c.imageHeight,
                asset_face.c.boundingBoxX1,
                asset_face.c.boundingBoxY1,
                asset_face.c.boundingBoxX2,
                asset_face.c.boundingBoxY2,
            )
            .select_from(named_face)
            .where(
                asset_face.c.assetId == asset_row.id,
                visible_face,
                person.c.name != "",
                person.c.isHidden.is_(False),
            )
        )
        face_rows = conn.execute(faces_stmt).all()

    faces = [row_to_face(row) for row in face_rows]
    if len(faces) <= max_faces:
        return faces
    # More named faces than the cap - hide a random number of them between 1 and max_faces,
    # not always exactly max_faces (see docstring).
    return random.sample(faces, random.randint(1, max_faces))
