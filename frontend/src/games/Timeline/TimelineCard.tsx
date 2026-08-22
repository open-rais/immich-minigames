import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"

import { assetThumbnailUrl } from "../../api/games"
import { Spinner } from "../shared/Spinner"
import { useQueuedThumbnail } from "../shared/thumbnailQueue"

// Mirrors MoreOrLess/PersonPhoto.tsx's failed-image placeholder pattern.
const placeholderStyle = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-placeholder-a), var(--color-placeholder-a) 10px, var(--color-placeholder-b) 10px, var(--color-placeholder-b) 20px)",
}

// The central "card to place" is a plain AssetPhoto now (TimelineGame.tsx), not a TimelineCard -
// this component only renders track cards: the live-play track's small cards ("sm") and the
// "Ver rondas" track's bigger read-only cards ("md").
export type TimelineCardSize = "md" | "sm"
export type TimelineCardVariant = "default" | "correct" | "wrong"

// The one place both track sizes get their dimensions from - every track card is the same size
// regardless of how far apart its neighbors' dates are, so this is a fixed lookup, never computed
// from a date span.
const SIZE_CLASS: Record<TimelineCardSize, string> = {
  md: "w-44 h-64 md:w-52 md:h-72",
  sm: "w-28 h-40 md:w-32 md:h-44",
}

// Two lines (month/day, then year) - tall/large enough to read comfortably at the bigger card size.
const DATE_STRIP_CLASS: Record<TimelineCardSize, string> = {
  md: "h-12 text-base md:h-14 md:text-lg",
  sm: "h-11 text-sm md:h-12 md:text-base",
}

const VARIANT_BORDER: Record<TimelineCardVariant, string> = {
  default: "border-line",
  correct: "border-emerald-500",
  wrong: "border-rose-500",
}

// Both track sizes crop to fill the card (only the central AssetPhoto letterboxes).
const IMG_FIT_CLASS = "object-cover"

interface TimelineCardProps {
  assetId: string
  // null renders "?" - the card's date hasn't been revealed yet.
  date: string | null
  size?: TimelineCardSize
  variant?: TimelineCardVariant
  className?: string
  // "Ver rondas" only - the order this card was drawn in ("Inicio" for
  // the seed card, "#N" for round N's), rendered as a small pill over the top-left corner.
  badge?: string
  // "Ver rondas" only - a per-card menu (EntryOptionsMenu + "Ver en Immich"), rendered over the
  // top-right corner. Never set in live play.
  actions?: ReactNode
  // Live-play track only (TimelineTrack.tsx) - opens the full-photo view for an already-placed
  // card. Undefined for the central "card to place" (its own zoom lives directly on AssetPhoto in
  // TimelineGame.tsx) and for "Ver rondas" (whose actions menu already offers "Ver en Immich").
  onClick?: () => void
}

export function TimelineCard({
  assetId,
  date,
  size = "sm",
  variant = "default",
  className = "",
  badge,
  actions,
  onClick,
}: TimelineCardProps) {
  const { i18n } = useTranslation()
  const { url, failed } = useQueuedThumbnail(assetThumbnailUrl(assetId))

  // Two lines - "month, day" on top, "year" below - rather than one combined string, per the
  // roadmap's request for a taller/more legible date strip.
  const monthDay = date
    ? new Intl.DateTimeFormat(i18n.language, {
        month: "short",
        day: "numeric",
        timeZone: "UTC",
      }).format(new Date(date))
    : null
  const year = date
    ? new Intl.DateTimeFormat(i18n.language, { year: "numeric", timeZone: "UTC" }).format(
        new Date(date),
      )
    : null

  return (
    <div
      onClick={onClick}
      className={`relative flex flex-none flex-col overflow-hidden rounded-2xl border-2 bg-surface shadow-card ${VARIANT_BORDER[variant]} ${SIZE_CLASS[size]} ${onClick ? "cursor-pointer" : ""} ${className}`}
    >
      {badge && (
        <div className="absolute top-1.5 left-1.5 z-10 flex h-8 min-w-8 items-center justify-center rounded-full bg-black/60 px-2 text-xs font-bold text-white">
          {badge}
        </div>
      )}
      {actions && (
        // Just the dark circular backdrop for legibility over the photo - the trigger's own icon
        // color is forced white via EntryOptionsMenu's triggerClassName prop (TimelineRounds.tsx),
        // not a blanket `[&_button]` descendant selector here: that used to also catch the
        // popover's own row buttons (ImmichLink/ReportMenuItem) once opened, since they're still
        // DOM descendants of this div despite the popover itself being `position: fixed`.
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute top-1.5 right-1.5 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-black/40"
        >
          {actions}
        </div>
      )}
      <div className="relative flex-1 overflow-hidden bg-app-bg">
        {failed ? (
          <div className="absolute inset-0" style={placeholderStyle} />
        ) : url ? (
          <img
            src={url}
            alt=""
            draggable={false}
            className={`h-full w-full rounded-sm select-none ${IMG_FIT_CLASS}`}
          />
        ) : null}
        {!url && !failed && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Spinner className="h-6 w-6" />
          </div>
        )}
      </div>
      <div
        className={`flex flex-none flex-col items-center justify-center border-t border-line font-mono font-bold text-muted leading-tight ${DATE_STRIP_CLASS[size]}`}
      >
        {monthDay && year ? (
          <>
            <span>{monthDay}</span>
            <span>{year}</span>
          </>
        ) : (
          <span>?</span>
        )}
      </div>
    </div>
  )
}
