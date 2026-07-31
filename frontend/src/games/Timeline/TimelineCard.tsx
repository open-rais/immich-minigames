import type { ReactNode } from "react"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { assetThumbnailUrl } from "../../api/games"

// Mirrors MoreOrLess/PersonPhoto.tsx's failed-image placeholder pattern.
const placeholderStyle = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-placeholder-a), var(--color-placeholder-a) 10px, var(--color-placeholder-b) 10px, var(--color-placeholder-b) 20px)",
}

export type TimelineCardSize = "lg" | "md" | "sm"
export type TimelineCardVariant = "default" | "correct" | "wrong"

// The one place both the big "card to place", the live-play track's small cards ("sm"), and the
// "Ver rondas" track's bigger read-only cards ("md") get their dimensions from - every track card
// is the same size regardless of how far apart its neighbors' dates are, so this
// is a fixed lookup, never computed from a date span. "sm" is wide enough on mobile that a full
// "MMM D, YYYY" date fits the strip on one line without truncating.
const SIZE_CLASS: Record<TimelineCardSize, string> = {
  lg: "w-64 h-80 md:w-72 md:h-96",
  md: "w-40 h-56 md:w-48 md:h-64",
  sm: "w-[92px] h-[126px] md:w-28 md:h-[150px]",
}

const DATE_STRIP_CLASS: Record<TimelineCardSize, string> = {
  lg: "h-8 text-sm md:h-9 md:text-base",
  md: "h-6 text-xs md:h-7 md:text-sm",
  sm: "h-5 text-[10px] md:h-6 md:text-xs",
}

const VARIANT_BORDER: Record<TimelineCardVariant, string> = {
  default: "border-line",
  correct: "border-emerald-500",
  wrong: "border-rose-500",
}

// The big center card shows the whole photo, letterboxed with a little breathing room - every
// track card (live "sm" or read-only "md") instead fills almost the entire card with its crop
// (only the date strip is exempt), since at that size a letterboxed photo would read as mostly
// empty card.
const PHOTO_WRAP_CLASS: Record<TimelineCardSize, string> = {
  lg: "p-3",
  md: "",
  sm: "",
}
const IMG_FIT_CLASS: Record<TimelineCardSize, string> = {
  lg: "object-contain",
  md: "object-cover",
  sm: "object-cover",
}

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
}

export function TimelineCard({
  assetId,
  date,
  size = "sm",
  variant = "default",
  className = "",
  badge,
  actions,
}: TimelineCardProps) {
  const { i18n } = useTranslation()
  const [failed, setFailed] = useState(false)
  const [loaded, setLoaded] = useState(false)

  // A caller that doesn't also key this component by assetId (it should - see TimelineGame.tsx/
  // TimelineTrack.tsx) would otherwise keep this same <img> node across a card swap: the browser
  // then keeps painting the OLD photo's bytes until the new ones finish downloading, instead of
  // showing nothing - a stale-image flash exactly at the moment a new round starts. Resetting here
  // too makes that safe even if a future caller forgets the key.
  useEffect(() => {
    setFailed(false)
    setLoaded(false)
  }, [assetId])

  const formattedDate = date
    ? new Intl.DateTimeFormat(i18n.language, {
        year: "numeric",
        month: "short",
        day: "numeric",
        timeZone: "UTC",
      }).format(new Date(date))
    : "?"

  return (
    <div
      className={`relative flex flex-none flex-col overflow-hidden rounded-2xl border-2 bg-surface shadow-card ${VARIANT_BORDER[variant]} ${SIZE_CLASS[size]} ${className}`}
    >
      {badge && (
        <div className="absolute top-1.5 left-1.5 z-10 flex h-8 min-w-8 items-center justify-center rounded-full bg-black/60 px-2 text-xs font-bold text-white">
          {badge}
        </div>
      )}
      {actions && (
        <div className="absolute top-1.5 right-1.5 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-black/40 [&_button]:text-white/90">
          {actions}
        </div>
      )}
      <div className={`relative flex-1 overflow-hidden bg-app-bg ${PHOTO_WRAP_CLASS[size]}`}>
        {failed ? (
          <div className="absolute inset-0" style={placeholderStyle} />
        ) : (
          <img
            key={assetId}
            src={assetThumbnailUrl(assetId)}
            alt=""
            draggable={false}
            onLoad={() => setLoaded(true)}
            onError={() => setFailed(true)}
            className={`h-full w-full rounded-sm select-none ${IMG_FIT_CLASS[size]} transition-opacity duration-150 ${loaded ? "opacity-100" : "opacity-0"}`}
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
