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

  // iOS Safari fix. This popover autofocuses its search input (PersonSearchInput), which opens the
  // software keyboard; because the popover is anchored near the tapped face - often low on the
  // screen - iOS force-scrolls the document up to reveal the input (it does this even though the
  // game shell is overflow-hidden). When the popover closes and the keyboard dismisses (the input
  // is removed from the DOM, which alone drops focus and closes the keyboard), Safari leaves that
  // residual window.scrollY in place *and* doesn't recompute the touch hit-regions of the fixed
  // game layer (AssetPhoto's `fixed inset-0`) or the fixed submit button, so every following tap
  // lands offset by that scroll amount - a dead zone the player could only clear by pinch-zooming
  // the whole page. Snapping scroll back to the origin as the popover unmounts (any close path:
  // guess picked, outside tap, or reveal) realigns the layout and visual viewports and restores tap
  // handling. Deliberately no blur() here: it would fire on StrictMode's dev-only mount-time
  // setup/cleanup/setup double-invoke and steal focus from the just-autofocused input. A no-op on
  // browsers without the quirk (scrollY already 0).
  useEffect(() => {
    return () => window.scrollTo(0, 0)
  }, [])

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
