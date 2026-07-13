import type { ReactNode } from "react"

import { PersonPhoto } from "./PersonPhoto"

interface StatCardProps {
  thumbnailUrl: string
  name: string
  subtitle: string
  children: ReactNode
}

/**
 * Shared shell for both the (always-revealed) reference card and the (interactive) candidate
 * card - photo, name, a subtitle line, and an action row, each row a fixed min-height so two
 * cards side by side (or stacked) always end up the same total height regardless of how much
 * their name/subtitle text wraps.
 */
export function StatCard({ thumbnailUrl, name, subtitle, children }: StatCardProps) {
  return (
    <div className="flex h-full min-h-0 w-full flex-col items-center gap-3.5 rounded-[22px] border border-line bg-white p-[18px] shadow-card md:h-auto md:w-[300px] md:rounded-3xl md:p-5">
      <PersonPhoto src={thumbnailUrl} alt={name} />

      <div className="flex min-h-[56px] w-full items-center justify-center">
        <div className="text-center text-xl font-bold text-ink">{name}</div>
      </div>

      <div className="flex min-h-[44px] w-full items-center justify-center">
        <p className="text-center text-sm font-semibold text-muted">{subtitle}</p>
      </div>

      <div className="flex min-h-[52px] w-full items-center justify-center">{children}</div>
    </div>
  )
}
