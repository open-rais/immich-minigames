import { useState } from "react"

const placeholderStyle = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-placeholder-a), var(--color-placeholder-a) 10px, var(--color-placeholder-b) 10px, var(--color-placeholder-b) 20px)",
}

export function PersonPhoto({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return <div className="aspect-square w-full rounded-2xl" style={placeholderStyle} />
  }

  return (
    <img src={src} alt={alt} onError={() => setFailed(true)} className="aspect-square w-full rounded-2xl object-cover" />
  )
}
