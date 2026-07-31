import type { RefObject } from "react"
import { useEffect, useState } from "react"

import type { Size } from "./fitBox"

// Tracks an element's own rendered size via ResizeObserver - null until the first observation
// fires. Takes an existing ref rather than creating its own so callers that also need the element
// for other purposes (pointer handlers, getBoundingClientRect) keep a single ref (AssetPhoto.tsx;
// TimelineRuler.tsx's own containerWidth tracking follows the same convention, see A-2).
export function useElementSize<T extends HTMLElement>(ref: RefObject<T | null>): Size | null {
  const [size, setSize] = useState<Size | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      setSize({ width, height })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [ref])

  return size
}
