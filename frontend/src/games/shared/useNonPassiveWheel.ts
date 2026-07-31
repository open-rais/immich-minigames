import type { RefObject } from "react"
import { useEffect, useRef } from "react"

// React marks onWheel as a passive listener by default, so preventDefault() inside a JSX handler
// silently does nothing (and warns) - attaching natively is the only way to actually stop the page
// from scrolling/zooming while a pan/zoom surface (AssetPhoto.tsx, TimelineRuler.tsx) handles the
// gesture itself. The handler is kept in a ref so this only attaches once
// per element instead of re-subscribing whenever the caller's own state changes.
export function useNonPassiveWheel<T extends HTMLElement>(
  ref: RefObject<T | null>,
  handler: (e: WheelEvent) => void,
) {
  const handlerRef = useRef(handler)
  handlerRef.current = handler

  useEffect(() => {
    const el = ref.current
    if (!el) return
    function onWheel(e: WheelEvent) {
      handlerRef.current(e)
    }
    el.addEventListener("wheel", onWheel, { passive: false })
    return () => el.removeEventListener("wheel", onWheel)
  }, [ref])
}
