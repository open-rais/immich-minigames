import { useState } from "react"

const placeholderStyle = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-placeholder-a), var(--color-placeholder-a) 10px, var(--color-placeholder-b) 10px, var(--color-placeholder-b) 20px)",
}

// Square on every breakpoint (a rectangular crop cuts off faces). On mobile the card has to fit
// the viewport with no scroll, so the photo is the flexible element: it grows to fill whatever
// vertical space the card has left after its fixed-height rows, capped at max-h-40 so it doesn't
// balloon on a tall/short-content screen. Desktop keeps its fixed 300x300 sizing (`w-full`).
const sizingClass =
  "aspect-square max-h-40 min-h-0 w-auto flex-1 rounded-[14px] md:h-auto md:w-full md:max-h-none md:flex-none md:rounded-2xl"

export function PersonPhoto({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return <div className={sizingClass} style={placeholderStyle} />
  }

  return <img src={src} alt={alt} onError={() => setFailed(true)} className={`${sizingClass} object-cover`} />
}
