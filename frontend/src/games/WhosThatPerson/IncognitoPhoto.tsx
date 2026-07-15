import type { CSSProperties } from "react"
import { useLayoutEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"

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
// guessing a bit harder than a tight crop that outlines the exact face shape. Tweak this value
// directly to change how much extra padding every box gets.
const BOX_EXPAND_RATIO = 0.15

// A detection box that's a tiny fraction of the photo (a face far in the background of a group
// shot) renders as a near-invisible, barely-tappable rectangle - and the "grow toward bottom-right
// only" percentage sizing model makes it drift visibly off the actual face at small sizes too.
// Enforcing this floor (via CSS `max()`, so it never shrinks below it regardless of the photo's
// rendered size) and re-centering around it keeps every box tappable and visually anchored on the
// face it hides, matching the >=44px touch-target guideline.
const MIN_BOX_PX = 44

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
// at any zoom/pan state. Width/height are floored at MIN_BOX_PX via CSS `max()` (mixing % and px is
// valid - the browser resolves both to lengths at layout and picks the larger), and left/top are
// pulled back by half of whatever that floor added so the box grows symmetrically around its
// original center instead of only toward the bottom-right. `--box-w`/`--box-h` custom properties
// let the left/top `calc()`s below reuse the exact same `max()` result the width/height use, rather
// than duplicating (and potentially drifting from) that expression.
function boxStyle(face: HiddenFaceOut): CSSProperties {
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

// The popover's own footprint, mirroring its old `w-[min(80vw,280px)]` Tailwind class now that
// width is computed in JS instead.
const POPOVER_MAX_WIDTH_PX = 280
const POPOVER_GAP_PX = 8 // mirrors the old mt-2/mb-2 (0.5rem)
const POPOVER_VIEWPORT_MARGIN_PX = 12
// The search input's own height - the minimum slice of the popover that must stay on-screen for it
// to still be usable, even when the tapped box leaves near-zero room on both sides (see
// popoverFixedStyle below). Only this much is guaranteed; the results dropdown below the input
// scrolls internally if it runs out of room (see PersonSearchInput.tsx's own max-h/overflow-y-auto)
// rather than this popover being capped/scrolled as a whole - the input itself must never be part
// of a scrolled region, or it reads as "the search bar is broken" rather than "there's a list below
// it".
const POPOVER_MIN_VISIBLE_PX = 56

// Anchors the popover to the face box's real on-screen position (from getBoundingClientRect(),
// measured once when the box is tapped - see FaceBox's useLayoutEffect) rather than the box's own
// percentage position within the photo: the popover is portaled out to <body> specifically so it
// escapes the photo's zoom/pan transform (see FaceGuessPopover.tsx), so it needs plain viewport
// pixels, not a position relative to the (transformed) box.
function popoverFixedStyle(anchor: DOMRect): CSSProperties {
  const width = Math.min(window.innerWidth * 0.8, POPOVER_MAX_WIDTH_PX)

  // A heavily zoomed-in box can have a real rect that extends well beyond the viewport (the
  // photo's own container only clips it visually via overflow-hidden - getBoundingClientRect()
  // still reports the untruncated rect), so anchoring off its raw edges can place the popover
  // off-screen. Clamp to the visible slice - the part of the box the player could actually see and
  // tap - before using it for placement.
  const visibleLeft = Math.max(anchor.left, 0)
  const visibleRight = Math.min(anchor.right, window.innerWidth)
  const visibleTop = Math.max(anchor.top, 0)
  const visibleBottom = Math.min(anchor.bottom, window.innerHeight)

  // Whichever side of the visible box has more room wins, rather than a fixed "is the box past
  // 60% down the screen" cutoff - a heavily zoomed-in box can fill most of the viewport, at which
  // point a fixed ratio on its top edge alone no longer reflects which side actually has space
  // (e.g. a box whose visible top sits at 36% down the screen but whose visible bottom already
  // touches the viewport's edge has zero room below despite failing that ratio check).
  //
  // Clamped so at least POPOVER_MIN_VISIBLE_PX stays on-screen on the chosen side - previously this
  // only capped at POPOVER_VIEWPORT_MARGIN_PX past the box's own edge, so a box that left almost no
  // room on either side (any face box once zoomed in enough) could pin the popover's top edge just
  // shy of the opposite edge of the screen, pushing its whole body - search input included - off
  // the visible viewport.
  const spaceAbove = visibleTop
  const spaceBelow = window.innerHeight - visibleBottom
  const vertical =
    spaceBelow >= spaceAbove
      ? {
          top: Math.min(
            Math.max(visibleBottom + POPOVER_GAP_PX, POPOVER_VIEWPORT_MARGIN_PX),
            window.innerHeight - POPOVER_MIN_VISIBLE_PX - POPOVER_VIEWPORT_MARGIN_PX,
          ),
        }
      : {
          bottom: Math.min(
            Math.max(window.innerHeight - visibleTop + POPOVER_GAP_PX, POPOVER_VIEWPORT_MARGIN_PX),
            window.innerHeight - POPOVER_MIN_VISIBLE_PX - POPOVER_VIEWPORT_MARGIN_PX,
          ),
        }

  const centerXRatio = (visibleLeft + visibleRight) / 2 / window.innerWidth
  const idealLeft =
    centerXRatio < 0.33
      ? visibleLeft
      : centerXRatio > 0.66
        ? visibleRight - width
        : (visibleLeft + visibleRight) / 2 - width / 2
  const left = Math.min(
    Math.max(idealLeft, POPOVER_VIEWPORT_MARGIN_PX),
    window.innerWidth - width - POPOVER_VIEWPORT_MARGIN_PX,
  )

  return { position: "fixed", left, width, ...vertical }
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

  const buttonRef = useRef<HTMLButtonElement>(null)
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null)

  // Measured once when the popover opens (not tracked continuously) - a pointerdown anywhere else
  // on the photo both pans it (AssetPhoto) and closes the popover (FaceGuessPopover's own outside-
  // pointerdown listener), so the anchor can't go stale while the popover stays open.
  useLayoutEffect(() => {
    setAnchorRect(active && phase === "guessing" && buttonRef.current ? buttonRef.current.getBoundingClientRect() : null)
  }, [active, phase])

  return (
    <div className="absolute" style={boxStyle(face)}>
      <div className="relative h-full w-full">
        <button
          ref={buttonRef}
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

        {active &&
          phase === "guessing" &&
          anchorRect &&
          createPortal(
            <FaceGuessPopover
              style={popoverFixedStyle(anchorRect)}
              onGuess={onGuess}
              onClose={() => onSelectFace(null)}
            />,
            document.body,
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
