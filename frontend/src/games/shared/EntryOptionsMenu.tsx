import type { ReactNode } from "react"
import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"

function DotsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <circle cx="5" cy="12" r="1.8" />
      <circle cx="12" cy="12" r="1.8" />
      <circle cx="19" cy="12" r="1.8" />
    </svg>
  )
}

interface EntryOptionsMenuProps {
  children: ReactNode
}

const POPOVER_WIDTH_PX = 192 // w-48
const POPOVER_GAP_PX = 8

// "..." trigger + popover for a compact row's per-entity actions -
// today just the "Ver en Immich" link, later joined by "Reportar" once that feature exists (no
// placeholder reserved for it yet). Same open/outside-click/Escape
// mechanics as menu/UserMenu.tsx's account popover, generalized to arbitrary row content instead
// of that component's fixed account/language/theme rows.
//
// The popover itself is positioned as `fixed`, computed from the trigger's own screen position,
// rather than `absolute` relative to this wrapper - this can open from inside a horizontally-
// scrollable container (Immichdle's GuessTable.tsx), whose own `overflow-x-auto` computes
// `overflow-y` to `auto` too (any ancestor with one axis non-`visible` forces the other to `auto`
// as well) and would otherwise silently clip anything `absolute` that spills past its content box.
// `fixed` ignores that entirely - nothing in this tree sets transform/filter/contain, the only
// things that would re-trap it - and the outside-click/Escape handlers below need no change for
// it (same DOM node, same ref; `.contains()` doesn't care about the node's visual position).
export function EntryOptionsMenu({ children }: EntryOptionsMenuProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [popoverPosition, setPopoverPosition] = useState<{ top: number; left: number } | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  // Measured synchronously before paint so the popover never flashes at the wrong spot on open.
  useLayoutEffect(() => {
    if (!open || !buttonRef.current) return
    const rect = buttonRef.current.getBoundingClientRect()
    setPopoverPosition({
      top: rect.bottom + POPOVER_GAP_PX,
      left: Math.max(POPOVER_GAP_PX, rect.right - POPOVER_WIDTH_PX),
    })
  }, [open])

  useEffect(() => {
    if (!open) return
    function handlePointerDown(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    // A `fixed` popover doesn't move with the page, so it'd visually detach from its trigger on
    // scroll - closing it is simpler than tracking position continuously. Capture phase so this
    // also catches scrolling a nested container (e.g. GuessTable's own horizontal scroll), which
    // doesn't bubble a "scroll" event up to document otherwise.
    function handleScroll() {
      setOpen(false)
    }
    document.addEventListener("pointerdown", handlePointerDown)
    document.addEventListener("keydown", handleKeyDown)
    document.addEventListener("scroll", handleScroll, true)
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown)
      document.removeEventListener("keydown", handleKeyDown)
      document.removeEventListener("scroll", handleScroll, true)
    }
  }, [open])

  return (
    <div ref={rootRef} className="relative flex-none">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={t("common.rounds.optionsMenu")}
        aria-expanded={open}
        className="flex h-8 w-8 items-center justify-center rounded-full text-muted transition-colors hover:bg-hover-tint hover:text-body"
      >
        <DotsIcon />
      </button>

      {open && popoverPosition && (
        <div
          style={{ top: popoverPosition.top, left: popoverPosition.left, width: POPOVER_WIDTH_PX }}
          className="fixed z-40 rounded-2xl border border-line bg-surface p-2 shadow-card"
        >
          {children}
        </div>
      )}
    </div>
  )
}
