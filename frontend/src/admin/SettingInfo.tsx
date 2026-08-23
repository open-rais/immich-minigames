import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"

function InfoIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <line x1="12" y1="11" x2="12" y2="16.5" />
      <circle cx="12" cy="7.5" r="0.75" fill="currentColor" stroke="none" />
    </svg>
  )
}

interface SettingInfoProps {
  helpText: string
}

const POPOVER_WIDTH_PX = 256
const POPOVER_GAP_PX = 8

// "i" trigger + popover explaining one admin setting - same `fixed`-position-computed-from-
// getBoundingClientRect + outside-click/Escape/scroll-close mechanics as
// games/shared/EntryOptionsMenu.tsx (this repo's only other "popover that must escape an
// overflow-hidden ancestor" - SettingAccordion.tsx's body has exactly that while animating open).
// Opens on hover *or* click/focus (a touch-only admin has no hover) - a click "pins" it open so it
// survives the pointer leaving, until an outside click/Escape/scroll dismisses it like any other
// popover here.
export function SettingInfo({ helpText }: SettingInfoProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [pinned, setPinned] = useState(false)
  const [popoverPosition, setPopoverPosition] = useState<{ top: number; left: number } | null>(null)
  const rootRef = useRef<HTMLSpanElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  useLayoutEffect(() => {
    if (!open || !buttonRef.current) return
    const rect = buttonRef.current.getBoundingClientRect()
    setPopoverPosition({
      top: rect.bottom + POPOVER_GAP_PX,
      left: Math.max(POPOVER_GAP_PX, Math.min(rect.left, window.innerWidth - POPOVER_WIDTH_PX - POPOVER_GAP_PX)),
    })
  }, [open])

  useEffect(() => {
    if (!open) return
    function close() {
      setOpen(false)
      setPinned(false)
    }
    function handlePointerDown(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) close()
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") close()
    }
    // Same "a fixed popover doesn't move with the page" reasoning as EntryOptionsMenu - closing on
    // scroll is simpler than tracking position continuously. Capture phase so this also catches a
    // nested scroll container (e.g. the admin accordion body itself).
    document.addEventListener("pointerdown", handlePointerDown)
    document.addEventListener("keydown", handleKeyDown)
    document.addEventListener("scroll", close, true)
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown)
      document.removeEventListener("keydown", handleKeyDown)
      document.removeEventListener("scroll", close, true)
    }
  }, [open])

  function handleClick() {
    const next = !pinned
    setPinned(next)
    setOpen(next)
  }

  return (
    <span ref={rootRef} className="relative inline-flex">
      <button
        ref={buttonRef}
        type="button"
        aria-label={t("admin.games.settingsHelpLabel")}
        onPointerEnter={() => setOpen(true)}
        onPointerLeave={() => !pinned && setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => !pinned && setOpen(false)}
        onClick={handleClick}
        className="flex h-4 w-4 flex-none items-center justify-center rounded-full text-faint transition-colors hover:text-primary"
      >
        <InfoIcon />
      </button>

      {open && popoverPosition && (
        <div
          style={{ top: popoverPosition.top, left: popoverPosition.left, width: POPOVER_WIDTH_PX }}
          className="fixed z-40 rounded-2xl border border-line bg-surface p-3 text-xs leading-relaxed font-normal whitespace-pre-line text-body shadow-card"
        >
          {helpText}
        </div>
      )}
    </span>
  )
}
