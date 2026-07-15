import type { CSSProperties } from "react"

import { assetThumbnailUrl, personThumbnailUrl } from "../../api/games"
import type { HiddenFaceOut } from "../../api/types"
import { AssetPhoto } from "../shared/AssetPhoto"
import type { RoundPhase } from "../shared/useRoundGame"
import { FaceGuessPopover } from "./FaceGuessPopover"

interface IncognitoPhotoProps {
  assetId: string
  faces: HiddenFaceOut[]
  guesses: Record<string, string>
  activeFaceId: string | null
  onSelectFace: (faceId: string | null) => void
  onGuess: (faceId: string, personId: string) => void
  phase: RoundPhase
}

// Each side grows by this fraction of the box's own width/height, hiding a bit more of the
// surrounding context (hair, clothes, posture) than the raw detection box alone would - makes
// guessing a bit harder than a tight crop that outlines the exact face shape.
const BOX_EXPAND_RATIO = 0.3

function expandedBox(face: HiddenFaceOut) {
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
// at any zoom/pan state.
function boxStyle(face: HiddenFaceOut): CSSProperties {
  const box = expandedBox(face)
  return {
    left: `${(box.x1 / face.image_width) * 100}%`,
    top: `${(box.y1 / face.image_height) * 100}%`,
    width: `${((box.x2 - box.x1) / face.image_width) * 100}%`,
    height: `${((box.y2 - box.y1) / face.image_height) * 100}%`,
  }
}

// Cheap anchoring heuristic computed straight from the (expanded) box's own position (no DOM
// measurement): flip above the box once it's in the lower part of the photo, and hug whichever side
// it's closest to horizontally, so the popover doesn't get pushed off the visible photo for faces
// near an edge.
function popoverAnchorClass(face: HiddenFaceOut): string {
  const box = expandedBox(face)
  const centerY = (box.y1 + box.y2) / 2 / face.image_height
  const centerX = (box.x1 + box.x2) / 2 / face.image_width
  const vertical = centerY > 0.6 ? "bottom-full mb-2" : "top-full mt-2"
  const horizontal = centerX < 0.33 ? "left-0" : centerX > 0.66 ? "right-0" : "left-1/2 -translate-x-1/2"
  return `${vertical} ${horizontal}`
}

// One hidden face's overlay: a solid black box while unguessed (always black regardless of theme -
// this hides a face, it's not a themed UI surface), the guessed person's own thumbnail once a guess
// is picked, then (once revealed) that fill fades out - the real photo underneath was never actually
// altered, the box is purely an overlay - leaving a green/red border and the true name.
function FaceBox({
  face,
  guessedPersonId,
  active,
  onSelectFace,
  onGuess,
  phase,
}: {
  face: HiddenFaceOut
  guessedPersonId: string | undefined
  active: boolean
  onSelectFace: (faceId: string | null) => void
  onGuess: (personId: string) => void
  phase: RoundPhase
}) {
  const revealed = phase === "revealed"
  const borderClass = !revealed ? "border-white/80" : face.correct ? "border-clue-match" : "border-clue-miss"

  return (
    <div className="absolute" style={boxStyle(face)}>
      <div className="relative h-full w-full">
        <button
          type="button"
          disabled={phase !== "guessing"}
          onClick={() => onSelectFace(active ? null : face.face_id)}
          className={`h-full w-full overflow-hidden rounded-md border-2 transition-colors duration-500 disabled:cursor-default ${borderClass}`}
        >
          <div className={`h-full w-full transition-opacity duration-700 ease-out ${revealed ? "opacity-0" : "opacity-100"}`}>
            {guessedPersonId ? (
              <img src={personThumbnailUrl(guessedPersonId)} alt="" className="h-full w-full object-cover" />
            ) : (
              <div className="h-full w-full bg-blackout" />
            )}
          </div>
        </button>

        {revealed && face.person_name && (
          <span className="pointer-events-none absolute top-full left-1/2 z-10 mt-1.5 -translate-x-1/2 rounded-full bg-surface px-2.5 py-1 text-[11px] font-bold whitespace-nowrap text-ink shadow-card">
            {face.person_name}
          </span>
        )}

        {active && phase === "guessing" && (
          <FaceGuessPopover
            className={`absolute z-40 ${popoverAnchorClass(face)}`}
            onGuess={onGuess}
            onClose={() => onSelectFace(null)}
          />
        )}
      </div>
    </div>
  )
}

// Fullscreen, zoomable/pannable photo (same presentation as Geoguessr/Dateguessr's AssetCarousel,
// via the shared AssetPhoto) with the round's hidden faces overlaid on top, pixel-aligned at any
// zoom/pan state via AssetPhoto's `overlay` slot.
export function IncognitoPhoto({ assetId, faces, guesses, activeFaceId, onSelectFace, onGuess, phase }: IncognitoPhotoProps) {
  return (
    <AssetPhoto
      src={assetThumbnailUrl(assetId)}
      alt=""
      overlay={
        <>
          {/* Sits above the raw photo but below the face boxes - blocks right-click "save/open
              image" and dragging the underlying photo out, both of which would let a player see a
              hidden face without ever guessing it. */}
          <div className="absolute inset-0" onContextMenu={(e) => e.preventDefault()} onDragStart={(e) => e.preventDefault()} />
          {faces.map((face) => (
            <FaceBox
              key={face.face_id}
              face={face}
              guessedPersonId={guesses[face.face_id]}
              active={activeFaceId === face.face_id}
              onSelectFace={onSelectFace}
              onGuess={(personId) => onGuess(face.face_id, personId)}
              phase={phase}
            />
          ))}
        </>
      }
    />
  )
}
