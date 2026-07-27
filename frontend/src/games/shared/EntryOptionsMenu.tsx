import type { ReactNode } from "react"
import { useEffect, useRef, useState } from "react"
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

// "..." trigger + popover for a compact row's per-entity actions (ROUNDS-VIEW.md roadmap #10) -
// today just the "Ver en Immich" link, later joined by "Reportar" once that feature exists (no
// placeholder reserved for it yet, per the doc's own §3 H). Same open/outside-click/Escape
// mechanics as menu/UserMenu.tsx's account popover, generalized to arbitrary row content instead
// of that component's fixed account/language/theme rows.
export function EntryOptionsMenu({ children }: EntryOptionsMenuProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handlePointerDown(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("pointerdown", handlePointerDown)
    document.addEventListener("keydown", handleKeyDown)
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown)
      document.removeEventListener("keydown", handleKeyDown)
    }
  }, [open])

  return (
    <div ref={rootRef} className="relative flex-none">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={t("common.rounds.optionsMenu")}
        aria-expanded={open}
        className="flex h-8 w-8 items-center justify-center rounded-full text-muted transition-colors hover:bg-hover-tint hover:text-body"
      >
        <DotsIcon />
      </button>

      {open && (
        <div className="absolute top-[calc(100%+8px)] right-0 z-40 w-48 rounded-2xl border border-line bg-surface p-2 shadow-card">
          {children}
        </div>
      )}
    </div>
  )
}
