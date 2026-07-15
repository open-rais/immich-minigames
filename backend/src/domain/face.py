"""Corresponds to a detected face in an Immich asset (asset_face row)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Face:
    id: UUID
    asset_id: UUID
    person_id: UUID
    person_name: str
    # Resolution the face detection was computed on - not necessarily the asset's own resolution,
    # see persistence/immich_tables.py's asset_face comment.
    image_width: int
    image_height: int
    bounding_box_x1: int
    bounding_box_y1: int
    bounding_box_x2: int
    bounding_box_y2: int
