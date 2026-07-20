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

  return (
    <div
      className={`${nested ? "mt-3 rounded-xl border border-line" : "mt-4 rounded-2xl border-2 border-primary/20"} px-6 py-4 transition-all`}
    >
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex w-full place-items-center justify-between text-start">
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
        <div className={`grid transition-[grid-template-rows] duration-300 ease-out ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
          <div className="overflow-hidden">
            <div className="pt-4">{children}</div>
          </div>
        </div>
      )}
    </div>
  )
}
