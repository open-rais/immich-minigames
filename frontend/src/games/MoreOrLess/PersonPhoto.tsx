import { useState } from "react"

const placeholderStyle = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-placeholder-a), var(--color-placeholder-a) 10px, var(--color-placeholder-b) 10px, var(--color-placeholder-b) 20px)",
}

// Square on every breakpoint (a rectangular crop cuts off faces). On mobile, photo has fixed
// h-24 to prevent layout shift when switching between guess buttons and count badge. Desktop keeps
// its fixed 300x300 sizing (`w-full`).
const sizingClass =
  "aspect-square h-24 w-24 rounded-[14px] md:h-auto md:w-full md:max-h-none md:flex-none md:rounded-2xl"

export function PersonPhoto({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return <div className={sizingClass} style={placeholderStyle} />
  }

  return <img src={src} alt={alt} onError={() => setFailed(true)} className={`${sizingClass} object-cover`} />
}
