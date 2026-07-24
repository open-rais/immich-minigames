import { useState } from "react"

// Small round avatar for a guess row / search result - same failed-image placeholder convention as
// games/MoreOrLess/PersonPhoto.tsx and games/shared/AssetPhoto.tsx, just compact and circular
// instead of a full card photo.
const placeholderStyle = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-placeholder-a), var(--color-placeholder-a) 6px, var(--color-placeholder-b) 6px, var(--color-placeholder-b) 12px)",
}

// "sm" (default) is the compact size used in rows/results; "lg" is for a standalone hero reveal
// (e.g. Immichdle's finished screen showing who the mystery person was).
const SIZE_CLASSES = {
  sm: "h-10 w-10 md:h-14 md:w-14",
  lg: "h-24 w-24 md:h-32 md:w-32",
} as const

// `src: null` (e.g. a leaderboard entry with no skin picked, see menu/LeaderboardPage.tsx) renders
// the same placeholder as a failed image load - both mean "no photo to show".
export function PersonAvatar({ src, alt, size = "sm" }: { src: string | null; alt: string; size?: keyof typeof SIZE_CLASSES }) {
  const [failed, setFailed] = useState(false)
  const sizingClass = `${SIZE_CLASSES[size]} flex-none rounded-full`

  if (!src || failed) {
    return <div className={sizingClass} style={placeholderStyle} />
  }

  return <img src={src} alt={alt} onError={() => setFailed(true)} className={`${sizingClass} object-cover`} />
}
