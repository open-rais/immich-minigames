import type { CSSProperties } from "react"

// Shared by IncognitoPhoto.tsx's live FaceBox and FaceBoxReadOnly.tsx's rounds-review counterpart -
// the box geometry itself, no popover/anchor/tap logic (that stays
// in IncognitoPhoto.tsx, which the review doesn't need at all).

// Only the box-geometry fields are touched here - both HiddenFaceOut and any future caller already
// satisfy this.
interface FaceGeometry {
  bounding_box_x1: number
  bounding_box_y1: number
  bounding_box_x2: number
  bounding_box_y2: number
  image_width: number
  image_height: number
}

// Admin-configurable (games/whos_that_person/settings.py's face_box_growth) - a multiplicative
// factor on the box's own width/height (1.0 = the raw detection box, 1.5 = 1.5x it), hiding a bit
// more of the surrounding context (hair, clothes, posture) than a tight crop would, making guessing
// a bit harder. Fallback for a game loaded before this setting existed (GameOut.face_box_growth
// null) - same value as the backend's own default (games/whos_that_person/game.py's
// FACE_BOX_GROWTH), so an old game renders exactly as it used to.
export const DEFAULT_FACE_BOX_GROWTH = 1.3

export function expandedBox(face: FaceGeometry, growthFactor: number) {
  const boxWidth = face.bounding_box_x2 - face.bounding_box_x1
  const boxHeight = face.bounding_box_y2 - face.bounding_box_y1
  // growthFactor is the total multiplicative growth (1.0-1.5); the padding is applied per side, so
  // only half of the factor's excess goes on each edge.
  const padRatio = (growthFactor - 1) / 2
  const padX = boxWidth * padRatio
  const padY = boxHeight * padRatio
  return {
    x1: Math.max(0, face.bounding_box_x1 - padX),
    y1: Math.max(0, face.bounding_box_y1 - padY),
    x2: Math.min(face.image_width, face.bounding_box_x2 + padX),
    y2: Math.min(face.image_height, face.bounding_box_y2 + padY),
  }
}

// Percentage box (expanded, see above) relative to the face's own detection resolution - the layer
// this is placed in (AssetPhoto's `overlay`) is sized/positioned to exactly match the photo's
// rendered content box, so plain percentages line up with no further offset/letterbox math needed,
// at any zoom/pan state. No pixel floor here (there used to be one, MIN_BOX_PX - removed together
// with this setting: it broke symmetry for small boxes and made a growthFactor of 1.0 not actually
// mean "the raw detection box" for them) - a box too small to tap comfortably is handled by
// AssetPhoto's own zoom/pan instead.
export function boxStyle(face: FaceGeometry, growthFactor: number): CSSProperties {
  const box = expandedBox(face, growthFactor)
  return {
    left: `${(box.x1 / face.image_width) * 100}%`,
    top: `${(box.y1 / face.image_height) * 100}%`,
    width: `${((box.x2 - box.x1) / face.image_width) * 100}%`,
    height: `${((box.y2 - box.y1) / face.image_height) * 100}%`,
  }
}
