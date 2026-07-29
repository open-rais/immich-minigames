import { useState } from "react"
import { useTranslation } from "react-i18next"

import { assetThumbnailUrl } from "../../api/games"

// Mirrors MoreOrLess/PersonPhoto.tsx's failed-image placeholder pattern.
const placeholderStyle = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-placeholder-a), var(--color-placeholder-a) 10px, var(--color-placeholder-b) 10px, var(--color-placeholder-b) 20px)",
}

export type TimelineCardSize = "lg" | "sm"
export type TimelineCardVariant = "default" | "correct" | "wrong"

// The one place both the big "card to place" and the track's small cards get their dimensions from
// - decision [K]: every small card is the same size regardless of how far apart its neighbors'
// dates are, so this is a fixed lookup, never computed from a date span.
const SIZE_CLASS: Record<TimelineCardSize, string> = {
  lg: "w-44 h-60 md:w-56 md:h-72",
  sm: "w-[76px] h-[104px] md:w-24 md:h-32",
}

const DATE_STRIP_CLASS: Record<TimelineCardSize, string> = {
  lg: "h-8 text-sm md:h-9 md:text-base",
  sm: "h-5 text-[10px] md:h-6 md:text-xs",
}

const VARIANT_BORDER: Record<TimelineCardVariant, string> = {
  default: "border-line",
  correct: "border-emerald-500",
  wrong: "border-rose-500",
}

interface TimelineCardProps {
  assetId: string
  // null renders "?" - the card's date hasn't been revealed yet (docs/TODO/TIMELINE.md decision [H]).
  date: string | null
  size?: TimelineCardSize
  variant?: TimelineCardVariant
  className?: string
}

export function TimelineCard({ assetId, date, size = "sm", variant = "default", className = "" }: TimelineCardProps) {
  const { i18n } = useTranslation()
  const [failed, setFailed] = useState(false)

  const formattedDate = date
    ? new Intl.DateTimeFormat(i18n.language, { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }).format(
        new Date(date),
      )
    : "?"

  return (
    <div
      className={`flex flex-none flex-col overflow-hidden rounded-2xl border-2 bg-surface shadow-card ${VARIANT_BORDER[variant]} ${SIZE_CLASS[size]} ${className}`}
    >
      <div className="relative flex-1 overflow-hidden bg-app-bg">
        {failed ? (
          <div className="absolute inset-0" style={placeholderStyle} />
        ) : (
          <img
            src={assetThumbnailUrl(assetId)}
            alt=""
            draggable={false}
            onError={() => setFailed(true)}
            className="h-full w-full object-cover select-none"
          />
        )}
      </div>
      <div
        className={`flex flex-none items-center justify-center border-t border-line font-mono font-bold text-muted ${DATE_STRIP_CLASS[size]}`}
      >
        {formattedDate}
      </div>
    </div>
  )
}
