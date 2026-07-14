import { useState } from "react"

// Small round avatar for a guess row / search result - same failed-image placeholder convention as
// games/MoreOrLess/PersonPhoto.tsx and games/shared/AssetPhoto.tsx, just compact and circular
// instead of a full card photo.
const placeholderStyle = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-placeholder-a), var(--color-placeholder-a) 6px, var(--color-placeholder-b) 6px, var(--color-placeholder-b) 12px)",
}

export function PersonAvatar({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false)
  const sizingClass = "h-10 w-10 flex-none rounded-full md:h-12 md:w-12"

  if (failed) {
    return <div className={sizingClass} style={placeholderStyle} />
  }

  return <img src={src} alt={alt} onError={() => setFailed(true)} className={`${sizingClass} object-cover`} />
}
