import type { CSSProperties } from "react"
import { useEffect, useRef } from "react"

import { PersonSearchInput } from "../shared/PersonSearchInput"

// Stable reference (not a literal `new Set()` per render) - PersonSearchInput's debounced search
// effect depends on this by reference, so a fresh Set every render would reset its debounce timer on
// every unrelated re-render of this popover.
const EMPTY_EXCLUDE_IDS = new Set<string>()

interface FaceGuessPopoverProps {
  style: CSSProperties
  onGuess: (personId: string) => void
  onClose: () => void
}

// Floating panel anchored to a clicked face box (see IncognitoPhoto.tsx's popoverFixedStyle) -
// wraps the shared PersonSearchInput. Portaled to <body> and positioned with `style` (fixed,
// viewport-space coordinates measured from the box's real position) rather than being laid out
// inside the photo's own zoom/pan transform - nested there, the popover's fixed CSS size would get
// scaled up right along with the photo whenever the player zoomed in. Deliberately not excluding
// already-guessed people the way Immichdle's guess bar does: the same person can legitimately be
// the correct answer for two different faces in one photo (mirrors, collages - see
// backend/src/games/whos_that_person.py's module docstring), so every search always shows every
// match.
export function FaceGuessPopover({ style, onGuess, onClose }: FaceGuessPopoverProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handlePointerDown(e: PointerEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener("pointerdown", handlePointerDown)
    return () => document.removeEventListener("pointerdown", handlePointerDown)
  }, [onClose])

  function pick(personId: string) {
    onGuess(personId)
    onClose()
  }

  return (
    <div
      ref={containerRef}
      onClick={(e) => e.stopPropagation()}
      style={style}
      className="z-40 rounded-2xl border border-line bg-surface p-2 shadow-card"
    >
      <PersonSearchInput excludeIds={EMPTY_EXCLUDE_IDS} onSelect={pick} disabled={false} />
    </div>
  )
}
