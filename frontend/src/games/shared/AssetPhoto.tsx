import { useEffect, useRef, useState } from "react"

// Mirrors games/MoreOrLess/PersonPhoto.tsx's failed-image placeholder pattern, fullscreen instead
// of a card.
const placeholderStyle = {
  backgroundImage:
    "repeating-linear-gradient(135deg, var(--color-placeholder-a), var(--color-placeholder-a) 10px, var(--color-placeholder-b) 10px, var(--color-placeholder-b) 20px)",
}

// Same "zoom anchored under the cursor/pinch midpoint" UX principle as
// games/Dateguessr/TimelineRuler.tsx, just 2D (translate x/y + scale) instead of its 1D
// pixels-per-day/center-day - mirrors its wheel/pointer handling approach directly.
const MIN_SCALE = 1
const MAX_SCALE = 4
const WHEEL_ZOOM_SENSITIVITY = 0.0015

interface Point {
  x: number
  y: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

// object-contain (not object-cover) so the whole photo is always visible, letterboxed against the
// app's own bg token - matches how Immich's own fullscreen viewer shows a photo (not cropping it
// to fill the viewport).
export function AssetPhoto({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const [scale, setScale] = useState(1)
  const [translate, setTranslate] = useState<Point>({ x: 0, y: 0 })
  // Mirrors TimelineRuler.tsx's centerDayIndexRef - lets the native wheel listener (only attached
  // once, on mount) read the latest values without being in its dependency array.
  const scaleRef = useRef(scale)
  scaleRef.current = scale
  const translateRef = useRef(translate)
  translateRef.current = translate

  // Gesture bookkeeping - refs, not state, since they track in-progress pointer interactions
  // rather than anything that should trigger a re-render on their own. Same shape as
  // TimelineRuler.tsx's activePointersRef/dragRef/pinchRef.
  const activePointersRef = useRef<Map<number, Point>>(new Map())
  const dragRef = useRef<{ startClientX: number; startClientY: number; startTranslate: Point } | null>(null)
  const pinchRef = useRef<{ startDistance: number; startScale: number; startTranslate: Point; anchor: Point } | null>(
    null,
  )

  function clampTranslate(nextScale: number, next: Point): Point {
    const rect = containerRef.current?.getBoundingClientRect()
    const maxX = rect ? (Math.max(nextScale, MIN_SCALE) - 1) * (rect.width / 2) : 0
    const maxY = rect ? (Math.max(nextScale, MIN_SCALE) - 1) * (rect.height / 2) : 0
    return { x: clamp(next.x, -maxX, maxX), y: clamp(next.y, -maxY, maxY) }
  }

  // React marks onWheel as a passive listener by default, so preventDefault() inside a JSX handler
  // silently does nothing (and warns) - attaching natively is the only way to actually stop the
  // page from scrolling/zooming while the player zooms the photo. See TimelineRuler.tsx's own
  // wheel handler for the same rationale.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    function handleWheel(e: WheelEvent) {
      e.preventDefault()
      const rect = el!.getBoundingClientRect()
      const cursorX = e.clientX - rect.left - rect.width / 2
      const cursorY = e.clientY - rect.top - rect.height / 2
      setScale((prevScale) => {
        const factor = Math.exp(-e.deltaY * WHEEL_ZOOM_SENSITIVITY)
        const nextScale = clamp(prevScale * factor, MIN_SCALE, MAX_SCALE)
        const ratio = nextScale / prevScale
        setTranslate((prevTranslate) =>
          clampTranslate(nextScale, {
            x: cursorX - (cursorX - prevTranslate.x) * ratio,
            y: cursorY - (cursorY - prevTranslate.y) * ratio,
          }),
        )
        return nextScale
      })
    }

    el.addEventListener("wheel", handleWheel, { passive: false })
    return () => el.removeEventListener("wheel", handleWheel)
  }, [])

  function handlePointerDown(e: React.PointerEvent<HTMLDivElement>) {
    e.currentTarget.setPointerCapture(e.pointerId)
    activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })

    if (activePointersRef.current.size === 1) {
      dragRef.current = { startClientX: e.clientX, startClientY: e.clientY, startTranslate: translateRef.current }
      pinchRef.current = null
    } else if (activePointersRef.current.size === 2) {
      dragRef.current = null
      const [p1, p2] = [...activePointersRef.current.values()]
      const distance = Math.max(Math.hypot(p1.x - p2.x, p1.y - p2.y), 1)
      const rect = containerRef.current!.getBoundingClientRect()
      pinchRef.current = {
        startDistance: distance,
        startScale: scaleRef.current,
        startTranslate: translateRef.current,
        anchor: {
          x: (p1.x + p2.x) / 2 - rect.left - rect.width / 2,
          y: (p1.y + p2.y) / 2 - rect.top - rect.height / 2,
        },
      }
    }
  }

  function handlePointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!activePointersRef.current.has(e.pointerId)) return
    activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })

    if (activePointersRef.current.size >= 2 && pinchRef.current) {
      const { startDistance, startScale, startTranslate, anchor } = pinchRef.current
      const [p1, p2] = [...activePointersRef.current.values()]
      const distance = Math.max(Math.hypot(p1.x - p2.x, p1.y - p2.y), 1)
      const nextScale = clamp(startScale * (distance / startDistance), MIN_SCALE, MAX_SCALE)
      const ratio = nextScale / startScale
      setScale(nextScale)
      setTranslate(
        clampTranslate(nextScale, {
          x: anchor.x - (anchor.x - startTranslate.x) * ratio,
          y: anchor.y - (anchor.y - startTranslate.y) * ratio,
        }),
      )
      return
    }

    if (activePointersRef.current.size === 1 && dragRef.current) {
      const { startClientX, startClientY, startTranslate } = dragRef.current
      setTranslate(
        clampTranslate(scaleRef.current, {
          x: startTranslate.x + (e.clientX - startClientX),
          y: startTranslate.y + (e.clientY - startClientY),
        }),
      )
    }
  }

  function handlePointerUp(e: React.PointerEvent<HTMLDivElement>) {
    activePointersRef.current.delete(e.pointerId)
    if (activePointersRef.current.size < 2) pinchRef.current = null
    if (activePointersRef.current.size === 0) {
      dragRef.current = null
    } else if (activePointersRef.current.size === 1) {
      // One finger remains after a pinch ends - restart drag tracking from it, same as
      // TimelineRuler.tsx's handlePointerUp.
      const [[, point]] = activePointersRef.current
      dragRef.current = { startClientX: point.x, startClientY: point.y, startTranslate: translateRef.current }
    }
  }

  if (failed) {
    return <div className="fixed inset-0" style={placeholderStyle} />
  }

  return (
    <div
      ref={containerRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      className="fixed inset-0 touch-none overflow-hidden bg-app-bg select-none"
    >
      <img
        src={src}
        alt={alt}
        onError={() => setFailed(true)}
        draggable={false}
        style={{ transform: `translate(${translate.x}px, ${translate.y}px) scale(${scale})` }}
        className="h-full w-full object-contain"
      />
    </div>
  )
}
