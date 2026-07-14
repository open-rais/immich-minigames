import type { ReactNode } from "react"

import { BackButton } from "../games/shared/BackButton"

// Centered-card shell shared by Login/Signup - same visual language as the game cards
// (StatCard.tsx: rounded-3xl border-line bg-white shadow-card) applied to a single form instead
// of a photo, mirroring the centered-card look of Immich's own login screen.
export function AuthCard({
  title,
  backLabel,
  onBack,
  children,
  footer,
}: {
  title: string
  backLabel: string
  onBack: () => void
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-app-bg px-6 py-10">
      <BackButton label={backLabel} onClick={onBack} />
      <div className="w-full max-w-sm rounded-3xl border border-line bg-white p-8 shadow-card">
        <h1 className="mb-6 text-center text-2xl font-bold text-ink">{title}</h1>
        {children}
      </div>
      {footer && <p className="mt-6 text-center text-sm text-muted">{footer}</p>}
    </div>
  )
}
