import { useState } from "react"

// Mirrors games/MoreOrLess/PersonPhoto.tsx's failed-image placeholder pattern, fullscreen instead
// of a card.
const placeholderStyle = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-placeholder-a), var(--color-placeholder-a) 10px, var(--color-placeholder-b) 10px, var(--color-placeholder-b) 20px)",
}

// object-contain (not object-cover) so the whole photo is always visible, letterboxed against the
// app's own light background token - matches how Immich's own fullscreen viewer shows a photo
// (not cropping it to fill the viewport), while staying in the app's current light theme (a dark
// backdrop can come back once a real dark mode exists - see docs/TODO/ROADMAP.md's "Modo oscuro").
export function AssetPhoto({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return <div className="fixed inset-0" style={placeholderStyle} />
  }

  return (
    <div className="fixed inset-0 bg-app-bg">
      <img src={src} alt={alt} onError={() => setFailed(true)} className="h-full w-full object-contain" />
    </div>
  )
}
