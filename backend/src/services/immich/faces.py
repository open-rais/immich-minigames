"""Postgres queries over Immich's `asset_face` table, joined with `person` for named faces."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Engine

from domain.face import Face
from persistence.immich_tables import asset, asset_face, person

from ._random import sample_by_id_pivot
from ._rows import row_to_face


def get_random_asset_with_named_faces(
    engine: Engine,
    *,
    exclude_asset_ids: frozenset[UUID] = frozenset(),
    exclude_person_ids: frozenset[UUID] = frozenset(),
) -> list[Face]:
    """Picks one random asset that has at least one visible, non-deleted face already assigned
    to a named, non-hidden person, then returns every one of that asset's named, non-hidden
    faces - which of them to actually black out for a Who'sThatPerson round is that game's own
    decision (games/whos_that_person/content.py::LiveContent.pick_round), not this query's.
    Faces without a name are never returned -
    there'd be nothing to grade against, so they're left unblacked in the photo, purely
    decorative. Hidden people (Immich's own `isHidden` flag) are excluded the same way
    get_persons/search_persons already exclude them from the guess search box - otherwise a
    round could black out a face the player has no way to search for and guess.
    `exclude_person_ids` follows the same reasoning but caller-driven (services/reports_service.py's
    open-report exclusion) - applied to both statements below, same as isHidden, so an asset whose
    only named face belongs to an excluded person is never picked, and an excluded person's face
    never appears among an otherwise-eligible asset's candidates. Empty list if no eligible asset
    exists (e.g. exclude_asset_ids/exclude_person_ids/the game's data pool is exhausted)."""
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
    if exclude_person_ids:
        asset_id_stmt = asset_id_stmt.where(person.c.id.notin_(exclude_person_ids))
    # GROUP BY (not DISTINCT) - the join produces one row per matching face, so this collapses
    # back to one row per asset before picking.
    asset_id_stmt = asset_id_stmt.group_by(asset.c.id)

    with engine.connect() as conn:
        # Pivot on asset.id (see services/immich/_random.py) instead of `ORDER BY random()`,
        # which would force a full scan+sort of every asset with at least one named face.
        asset_rows = sample_by_id_pivot(conn, asset_id_stmt, asset.c.id, 1)
        if not asset_rows:
            return []
        asset_row = asset_rows[0]

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
        if exclude_person_ids:
            faces_stmt = faces_stmt.where(person.c.id.notin_(exclude_person_ids))
        face_rows = conn.execute(faces_stmt).all()

    return [row_to_face(row) for row in face_rows]
