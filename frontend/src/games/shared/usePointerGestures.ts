import { useRef } from "react"

export interface Point {
  x: number
  y: number
}

interface PointerGestureCallbacks {
  disabled?: boolean
  // A drag: one active pointer, not started on an interactive descendant. Also re-fired (with the
  // remaining pointer's current position) when a pinch drops back to one finger - see the
  // pointerUp restart logic below, same "re-base the start point" effect as a fresh drag.
  onDragStart?: (point: Point) => void
  // `startPoint` is the drag's own start position (or the restart position above), constant across
  // a single drag - not the previous move's point, so consumers computing a delta don't drift.
  onDragMove?: (point: Point, startPoint: Point) => void
  // `moved` is the largest distance (px) reached from the drag's start - a consumer that wants tap
  // detection compares it against its own threshold; one isn't imposed here.
  onDragEnd?: (point: Point, moved: number) => void
  // A pinch: two active pointers. `a`/`b` are raw client coordinates - anchor/midpoint math is each
  // consumer's own decision (2D translate+scale for AssetPhoto, 1D pxPerDay/centerDay for
  // TimelineRuler), not shared here.
  onPinchStart?: (a: Point, b: Point) => void
  onPinchMove?: (a: Point, b: Point) => void
  onPinchEnd?: () => void
}

interface PointerGestureHandlers {
  onPointerDown: (e: React.PointerEvent) => void
  onPointerMove: (e: React.PointerEvent) => void
  onPointerUp: (e: React.PointerEvent) => void
  onPointerCancel: (e: React.PointerEvent) => void
}

// Shared pointer-gesture mechanics for pan/zoom surfaces - pointer
// capture, tracking active pointers, classifying one active pointer as a drag and two as a pinch,
// and restarting drag tracking from whichever pointer remains once a pinch drops to one. Reports
// only raw client coordinates; what a drag/pinch actually does (AssetPhoto.tsx's 2D translate+scale,
// TimelineRuler.tsx's 1D pxPerDay/centerDay) is each consumer's own callback, not shared here - this
// hook owns the event mechanics, not either view's design.
export function usePointerGestures({
  disabled = false,
  onDragStart,
  onDragMove,
  onDragEnd,
  onPinchStart,
  onPinchMove,
  onPinchEnd,
}: PointerGestureCallbacks): PointerGestureHandlers {
  const activePointersRef = useRef<Map<number, Point>>(new Map())
  const dragStartRef = useRef<Point | null>(null)
  const movedRef = useRef(0)
  const pinchActiveRef = useRef(false)

  function onPointerDown(e: React.PointerEvent) {
    if (disabled) return
    // Don't hijack interactive content nested inside the gesture surface (e.g. Who'sThatPerson's
    // face-box buttons, TimelineRuler's zoom buttons) into a drag - once an element calls
    // setPointerCapture, every subsequent event for that pointer (including the synthesized
    // `click`) redirects to it instead of whatever was actually pointed at.
    if ((e.target as HTMLElement).closest("button, input, a")) return
    e.currentTarget.setPointerCapture(e.pointerId)
    activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })

    if (activePointersRef.current.size === 1) {
      pinchActiveRef.current = false
      const point = { x: e.clientX, y: e.clientY }
      dragStartRef.current = point
      movedRef.current = 0
      onDragStart?.(point)
    } else if (activePointersRef.current.size === 2) {
      dragStartRef.current = null
      pinchActiveRef.current = true
      const [a, b] = [...activePointersRef.current.values()]
      onPinchStart?.(a, b)
    }
  }

  function onPointerMove(e: React.PointerEvent) {
    if (disabled || !activePointersRef.current.has(e.pointerId)) return
    activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })

    if (activePointersRef.current.size >= 2 && pinchActiveRef.current) {
      const [a, b] = [...activePointersRef.current.values()]
      onPinchMove?.(a, b)
      return
    }

    if (activePointersRef.current.size === 1 && dragStartRef.current) {
      const point = { x: e.clientX, y: e.clientY }
      movedRef.current = Math.max(
        movedRef.current,
        Math.hypot(point.x - dragStartRef.current.x, point.y - dragStartRef.current.y),
      )
      onDragMove?.(point, dragStartRef.current)
    }
  }

  function onPointerUp(e: React.PointerEvent) {
    const point = { x: e.clientX, y: e.clientY }
    if (!disabled && activePointersRef.current.size === 1 && dragStartRef.current) {
      onDragEnd?.(point, movedRef.current)
    }

    activePointersRef.current.delete(e.pointerId)
    if (activePointersRef.current.size < 2 && pinchActiveRef.current) {
      pinchActiveRef.current = false
      onPinchEnd?.()
    }
    if (activePointersRef.current.size === 0) {
      dragStartRef.current = null
    } else if (activePointersRef.current.size === 1) {
      // One finger remains after a pinch ends - restart drag tracking from it, marked as already
      // past any tap threshold (Infinity) so lifting that finger next doesn't misfire a tap.
      const [[, remaining]] = activePointersRef.current
      dragStartRef.current = remaining
      movedRef.current = Infinity
      onDragStart?.(remaining)
    }
  }

  return { onPointerDown, onPointerMove, onPointerUp, onPointerCancel: onPointerUp }
}
