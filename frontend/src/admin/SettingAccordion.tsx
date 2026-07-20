import { useState, type ReactNode } from "react"

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`transition-transform ${open ? "rotate-180" : ""}`}
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  )
}

interface SettingAccordionProps {
  icon?: ReactNode
  title: string
  description?: string
  children?: ReactNode
  // Top-level cards (Usuarios/Juegos) get the heavier tinted border + icon, matching Immich's own
  // System Settings cards (see immich-admin-front.png/.htm). Nested cards (one per game inside
  // "Juegos", see AdminPage.tsx) drop the icon and use a plain, thinner border instead - same
  // visual demotion Immich itself uses for a settings group's inner rows (e.g. Image Settings'
  // thumbnail/preview/fullsize sub-items).
  nested?: boolean
  defaultOpen?: boolean
}

export function SettingAccordion({ icon, title, description, children, nested = false, defaultOpen = false }: SettingAccordionProps) {
  const [open, setOpen] = useState(defaultOpen)
  // Mount children lazily on first expand, then keep them mounted (rather than tying presence
  // directly to `open`) - some children (AdminUserRow's PersonSearchInput, see admin/AdminUserRow
  // .tsx) autofocus an input as soon as they mount, which would fight over focus if every row's
  // content mounted upfront while still collapsed; keeping them mounted after first open also
  // means a row's in-progress edits survive collapsing/re-expanding it.
  const [hasOpened, setHasOpened] = useState(defaultOpen)
  // Tracks whether the *opening* grid-row transition has fully finished - while it's still
  // animating (or collapsed), the wrapper below needs overflow-hidden for the grow/shrink to look
  // right, but that same overflow-hidden also clips anything a child overlays outside its own flow
  // height, like PersonSearchInput's absolutely-positioned results dropdown (see AdminUserRow.tsx)
  // - the row's grid track only sizes to the *in-flow* content, so the dropdown got visually cut
  // off instead of floating over the rest of the page. Once fully open, overflow is dropped so
  // that dropdown can render unclipped; closing re-clips immediately (no dropdown is visible then
  // anyway) so the collapse animation still looks right.
  const [settled, setSettled] = useState(defaultOpen)

  function toggle() {
    setOpen((o) => !o)
    setHasOpened((h) => h || !open)
    if (open) setSettled(false)
  }

  return (
    <div
      className={`${nested ? "mt-3 rounded-xl border border-line" : "mt-4 rounded-2xl border-2 border-primary/20"} px-6 py-4 transition-all`}
    >
      <button type="button" onClick={toggle} aria-expanded={open} className="flex w-full place-items-center justify-between text-start">
        <div>
          <div className="flex place-items-center gap-2">
            {icon && <span className="text-primary">{icon}</span>}
            <h2 className="font-medium text-primary">{title}</h2>
          </div>
          {description && <p className="mt-1 text-sm text-muted">{description}</p>}
        </div>
        <div className="flex place-content-center place-items-center rounded-full p-3 text-muted transition-colors hover:bg-primary/10 hover:text-primary">
          <ChevronIcon open={open} />
        </div>
      </button>
      {/* Same grid-rows trick as menu/GameSection.tsx's game-list collapse: animates from 0fr to
          1fr instead of a hardcoded max-height, so it works no matter how tall the content ends up
          being. Padding (not margin) on the innermost div, since a margin there would still poke
          out past the 0fr row when collapsed. */}
      {children && (
        <div
          className={`grid transition-[grid-template-rows] duration-300 ease-out ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
          onTransitionEnd={() => open && setSettled(true)}
        >
          <div className={settled ? "" : "overflow-hidden"}>
            <div className="pt-4">{hasOpened && children}</div>
          </div>
        </div>
      )}
    </div>
  )
}
