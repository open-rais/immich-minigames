import type { ReactNode } from "react"
import { useEffect, useRef, useState } from "react"

import { fitBox as computeFitBox } from "./fitBox"
import type { Size } from "./fitBox"
import { useImageLoad } from "./imageLoading"
import { PhotoError } from "./PhotoError"
import { Spinner } from "./Spinner"
import { useElementSize } from "./useElementSize"
import { useNonPassiveWheel } from "./useNonPassiveWheel"
import type { Point } from "./usePointerGestures"
import { usePointerGestures } from "./usePointerGestures"

// Same "zoom anchored under the cursor/pinch midpoint" UX principle as
// games/Dateguessr/TimelineRuler.tsx, just 2D (translate x/y + scale) instead of its 1D
// pixels-per-day/center-day - both built on the same usePointerGestures/useNonPassiveWheel
// mechanics, applying them to a different transform.
const MIN_SCALE = 1
const MAX_SCALE = 4
const WHEEL_ZOOM_SENSITIVITY = 0.0015

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

// object-contain (not object-cover) so the whole photo is always visible, letterboxed against the
// app's own bg token - matches how Immich's own fullscreen viewer shows a photo (not cropping it
// to fill the viewport).
//
// `overlay` (optional) renders inside a layer sized and positioned to exactly match the photo's
// rendered content box (the object-contain "fit box", not the full letterboxed container, see
// fitBox.ts) - and inherits the same pan/zoom transform as the image, so interactive content
// placed on top of the photo (e.g. Who'sThatPerson's face boxes) stays pixel-aligned to it at any
// zoom/pan state.
// Fills its parent (`absolute inset-0`) rather than positioning itself against the viewport - the
// caller declares the box (typically `fixed inset-0`, or a smaller area like Dateguessr's
// above-the-ruler wrapper) so a `position: fixed` ancestor that isn't itself a containing block
// can't silently make that box a no-op (see AssetCarousel.tsx and each game's own wrapper).
export function AssetPhoto({
  src,
  alt,
  overlay,
  onReadyChange,
}: {
  src: string
  alt: string
  overlay?: ReactNode
  // Fired whenever "loaded or failed" changes - a caller that needs to know when this photo is
  // done loading (e.g. Trivium's location questions, which hold their countdown until every
  // photo on screen is ready) hooks into this instead of duplicating the load/error tracking
  // below. A failed load still counts as "ready": the error state it falls back to needs no
  // further waiting. Note that "failed" now means the whole retry budget is spent
  // (imageLoading.ts), so a photo that never arrives holds this back for a few attempts rather
  // than resolving on the first hiccup.
  onReadyChange?: (ready: boolean) => void
}) {
  // Load/timeout/retry lives in the shared hook - see its docstring for why an <img> alone can
  // sit on a spinner forever, and why a retry has to remount the element via `imgKey`.
  const { status, imgRef, imgKey, onLoad, onError, retry } = useImageLoad(src)
  const loaded = status === "loaded"
  const containerRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  const [translate, setTranslate] = useState<Point>({ x: 0, y: 0 })

  // Resets any pan/zoom left over from the previous photo (confirmed by the owner: Trivium's
  // location photo kept a pinch-zoom applied across rounds) for a caller that doesn't key this
  // component by src (AssetCarousel.tsx does; WhosThatPersonGame's IncognitoPhoto doesn't) and so
  // keeps this same node across a round change. A caller that *does* key by src never sees this
  // fire on a photo change at all - the whole component remounts, already starting fresh - so it's
  // only ever a no-op there. The matching reset of the load state lives in useImageLoad, which has
  // to check whether the new photo is already decoded before assuming it needs loading.
  useEffect(() => {
    setScale(1)
    setTranslate({ x: 0, y: 0 })
  }, [src])

  useEffect(() => {
    onReadyChange?.(status !== "loading")
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [status])

  // Natural (source) image size and the container's own rendered size - both needed to compute
  // fitBox below. Only relevant when `overlay` is used; harmless to always track otherwise.
  const [naturalSize, setNaturalSize] = useState<Size | null>(null)
  const containerSize = useElementSize(containerRef)
  // Read by the wheel/pinch handlers below, which need the latest scale/translate without
  // re-subscribing (wheel) or without it changing which callback closure fired mid-gesture (pinch).
  const scaleRef = useRef(scale)
  scaleRef.current = scale
  const translateRef = useRef(translate)
  translateRef.current = translate

  // Start-of-gesture snapshots - captured in onDragStart/onPinchStart below, read in the matching
  // .../Move callback. usePointerGestures owns pointer capture/classification; this component owns
  // what a drag/pinch actually does to translate+scale.
  const dragStartTranslateRef = useRef<Point>({ x: 0, y: 0 })
  const pinchStartRef = useRef<{
    startDistance: number
    startScale: number
    startTranslate: Point
    anchor: Point
  } | null>(null)

  // The object-contain "fit box": where the image's actual pixels render within the container,
  // excluding letterbox padding - see fitBox.ts.
  const fitBox = naturalSize && containerSize ? computeFitBox(naturalSize, containerSize) : null

  function clampTranslate(nextScale: number, next: Point): Point {
    const rect = containerRef.current?.getBoundingClientRect()
    const maxX = rect ? (Math.max(nextScale, MIN_SCALE) - 1) * (rect.width / 2) : 0
    const maxY = rect ? (Math.max(nextScale, MIN_SCALE) - 1) * (rect.height / 2) : 0
    return { x: clamp(next.x, -maxX, maxX), y: clamp(next.y, -maxY, maxY) }
  }

  useNonPassiveWheel(containerRef, (e) => {
    e.preventDefault()
    const rect = containerRef.current!.getBoundingClientRect()
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
  })

  const gesture = usePointerGestures({
    onDragStart: () => {
      dragStartTranslateRef.current = translateRef.current
    },
    onDragMove: (point, startPoint) => {
      setTranslate(
        clampTranslate(scaleRef.current, {
          x: dragStartTranslateRef.current.x + (point.x - startPoint.x),
          y: dragStartTranslateRef.current.y + (point.y - startPoint.y),
        }),
      )
    },
    onPinchStart: (a, b) => {
      const rect = containerRef.current!.getBoundingClientRect()
      pinchStartRef.current = {
        startDistance: Math.max(Math.hypot(a.x - b.x, a.y - b.y), 1),
        startScale: scaleRef.current,
        startTranslate: translateRef.current,
        anchor: {
          x: (a.x + b.x) / 2 - rect.left - rect.width / 2,
          y: (a.y + b.y) / 2 - rect.top - rect.height / 2,
        },
      }
    },
    onPinchMove: (a, b) => {
      if (!pinchStartRef.current) return
      const { startDistance, startScale, startTranslate, anchor } = pinchStartRef.current
      const distance = Math.max(Math.hypot(a.x - b.x, a.y - b.y), 1)
      const nextScale = clamp(startScale * (distance / startDistance), MIN_SCALE, MAX_SCALE)
      const ratio = nextScale / startScale
      setScale(nextScale)
      setTranslate(
        clampTranslate(nextScale, {
          x: anchor.x - (anchor.x - startTranslate.x) * ratio,
          y: anchor.y - (anchor.y - startTranslate.y) * ratio,
        }),
      )
    },
    onPinchEnd: () => {
      pinchStartRef.current = null
    },
  })

  if (status === "failed") {
    return <PhotoError onRetry={retry} />
  }

  // When there's an overlay to keep pixel-aligned to the photo (e.g. Who'sThatPerson's face
  // boxes), don't paint the photo until fitBox is ready to paint the overlay in the same frame -
  // otherwise the photo (which the <img> tag renders as soon as it has a src, independent of the
  // state updates fitBox depends on) is visible for a beat with no overlay on top of it.
  const photoReady = !overlay || fitBox !== null

  return (
    <div
      ref={containerRef}
      {...gesture}
      className="absolute inset-0 touch-none overflow-hidden bg-app-bg select-none"
    >
      <div
        style={{ transform: `translate(${translate.x}px, ${translate.y}px) scale(${scale})` }}
        className="relative h-full w-full"
      >
        <img
          // A retry has to be a brand-new element, not the same one with the same src reassigned -
          // that's the whole point of imgKey, see imageLoading.ts.
          key={imgKey}
          ref={imgRef}
          src={src}
          alt={alt}
          onError={onError}
          onLoad={(e) => {
            setNaturalSize({
              width: e.currentTarget.naturalWidth,
              height: e.currentTarget.naturalHeight,
            })
            onLoad()
          }}
          draggable={false}
          className={`h-full w-full object-contain transition-opacity duration-150 ${
            photoReady && loaded ? "opacity-100" : "invisible opacity-0"
          }`}
        />
        {overlay && fitBox && (
          <div
            className="absolute"
            style={{
              left: fitBox.left,
              top: fitBox.top,
              width: fitBox.width,
              height: fitBox.height,
            }}
          >
            {overlay}
          </div>
        )}
      </div>
      {/* Outside the pan/zoom-transformed div so it stays a fixed size, centered on the container
          regardless of the photo's current scale. */}
      {!loaded && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Spinner className="h-8 w-8" />
        </div>
      )}
    </div>
  )
}
