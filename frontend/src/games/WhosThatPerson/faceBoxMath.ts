import type { CSSProperties } from "react"

// Shared by IncognitoPhoto.tsx's live FaceBox and FaceBoxReadOnly.tsx's rounds-review counterpart
// (ROUNDS-VIEW.md roadmap #10) - the box geometry itself, no popover/anchor/tap logic (that stays
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

// Each side grows by this fraction of the box's own width/height, hiding a bit more of the
// surrounding context (hair, clothes, posture) than the raw detection box alone would - makes
// guessing a bit harder than a tight crop that outlines the exact face shape. Tweak this value
// directly to change how much extra padding every box gets.
export const BOX_EXPAND_RATIO = 0.15

// A detection box that's a tiny fraction of the photo (a face far in the background of a group
// shot) renders as a near-invisible, barely-tappable rectangle - and the "grow toward bottom-right
// only" percentage sizing model makes it drift visibly off the actual face at small sizes too.
// Enforcing this floor (via CSS `max()`, so it never shrinks below it regardless of the photo's
// rendered size) and re-centering around it keeps every box tappable and visually anchored on the
// face it hides, matching the >=44px touch-target guideline.
export const MIN_BOX_PX = 44

export function expandedBox(face: FaceGeometry) {
  const boxWidth = face.bounding_box_x2 - face.bounding_box_x1
  const boxHeight = face.bounding_box_y2 - face.bounding_box_y1
  const padX = boxWidth * BOX_EXPAND_RATIO
  const padY = boxHeight * BOX_EXPAND_RATIO
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
// at any zoom/pan state. Width/height are floored at MIN_BOX_PX via CSS `max()` (mixing % and px is
// valid - the browser resolves both to lengths at layout and picks the larger), and left/top are
// pulled back by half of whatever that floor added so the box grows symmetrically around its
// original center instead of only toward the bottom-right. `--box-w`/`--box-h` custom properties
// let the left/top `calc()`s below reuse the exact same `max()` result the width/height use, rather
// than duplicating (and potentially drifting from) that expression.
export function boxStyle(face: FaceGeometry): CSSProperties {
  const box = expandedBox(face)
  const leftPct = (box.x1 / face.image_width) * 100
  const topPct = (box.y1 / face.image_height) * 100
  const widthPct = ((box.x2 - box.x1) / face.image_width) * 100
  const heightPct = ((box.y2 - box.y1) / face.image_height) * 100
  return {
    "--box-w": `max(${widthPct}%, ${MIN_BOX_PX}px)`,
    "--box-h": `max(${heightPct}%, ${MIN_BOX_PX}px)`,
    width: "var(--box-w)",
    height: "var(--box-h)",
    left: `calc(${leftPct}% - (var(--box-w) - ${widthPct}%) / 2)`,
    top: `calc(${topPct}% - (var(--box-h) - ${heightPct}%) / 2)`,
  } as CSSProperties
}
