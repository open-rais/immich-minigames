import { useQueuedThumbnail } from "./thumbnailQueue"

// Small round avatar for a guess row / search result - same failed-image placeholder convention as
// games/MoreOrLess/PersonPhoto.tsx and games/shared/AssetPhoto.tsx, just compact and circular
// instead of a full card photo.
const placeholderStyle = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-placeholder-a), var(--color-placeholder-a) 6px, var(--color-placeholder-b) 6px, var(--color-placeholder-b) 12px)",
}

// "sm" (default) is the compact size used in rows/results; "md" is the same on mobile but a bit
// bigger on desktop (Immichdle's GuessTable/PersonCell, once its own column started growing to fill
// leftover desktop width - see guessTableColumns.ts's PERSON_COL - a same-size avatar there was
// swimming in space); "lg" is for a standalone hero reveal (e.g. Immichdle's finished screen showing
// who the mystery person was).
// "fluid" is "lg" that also answers to the size of the screen, for the photo tiles among Trivium's
// alternatives - four of them share a no-scroll screen with the question, so they take the smaller
// of a share of the width and of the (dynamic) height, capped at lg's desktop size. "fill" takes
// whatever square box its parent gives it, for a caller that sizes that box itself (Trivium's round
// face, sized by the space left over - see TriviumBoard.tsx). Every other avatar in the app lives
// in a scrolling column where height isn't contended, and should use a fixed size.
const SIZE_CLASSES = {
  sm: "h-10 w-10 md:h-14 md:w-14",
  md: "h-10 w-10 md:h-16 md:w-16",
  lg: "h-24 w-24 md:h-32 md:w-32",
  fluid: "size-[clamp(3rem,min(20vw,10dvh),8rem)]",
  fill: "size-full",
} as const

// `src: null` (e.g. a leaderboard entry with no skin picked, see menu/LeaderboardPage.tsx) renders
// the same placeholder as a failed image load - both mean "no photo to show".
export function PersonAvatar({
  src,
  alt,
  size = "sm",
}: {
  src: string | null
  alt: string
  size?: keyof typeof SIZE_CLASSES
}) {
  const { url, failed } = useQueuedThumbnail(src)
  const sizingClass = `${SIZE_CLASSES[size]} flex-none rounded-full`

  if (!url || failed) {
    return <div className={sizingClass} style={placeholderStyle} />
  }

  return <img src={url} alt={alt} className={`${sizingClass} object-cover`} />
}
