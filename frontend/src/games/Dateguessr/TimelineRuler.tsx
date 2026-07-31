import { useEffect, useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"

import { useNonPassiveWheel } from "../shared/useNonPassiveWheel"
import { usePointerGestures } from "../shared/usePointerGestures"
import {
  buildTicks,
  dayIndexToX as rulerDayIndexToX,
  easeOutCubic,
  xToDayIndex as rulerXToDayIndex,
} from "./rulerMath"
import type { Tick } from "./rulerMath"
import { dayIndexFromIso, isoFromDayIndex, todayDayIndex } from "./timeMath"

// Zoom is expressed as pixels-per-day, the direct analog of MapPicker.tsx's MapLibre zoom level -
// same "zoom anchored under the cursor/pinch midpoint" UX principle, implemented by hand here since
// this is a custom ruler rather than a map library.
const MIN_PX_PER_DAY = 0.02 // ~80+ years visible across a typical viewport
const MAX_PX_PER_DAY = 60 // a single day comfortably fills a tap target
const DEFAULT_PX_PER_DAY = 2.2 // starting zoom - months visible, matches the "month" LOD tier

const WHEEL_ZOOM_SENSITIVITY = 0.0015
const CLICK_MOVEMENT_THRESHOLD_PX = 6
const REVEAL_ANIMATION_MS = 500
// A fixed multiplicative
// step per click/tap, same "anchor stays put" principle as the wheel/pinch gestures below. Bigger
// than a single wheel tick on purpose - a button press is a deliberate, discrete action (not a
// continuous gesture the player can just keep doing), so it should visibly move the needle.
const ZOOM_BUTTON_FACTOR = 2.5
// Short and snappy - long enough that the jump reads as a move rather than a cut, short enough that
// mashing the button repeatedly doesn't feel laggy.
const ZOOM_BUTTON_ANIMATION_MS = 220
// After a reveal, the two markers should span roughly this fraction of the ruler's width once
// fitted - mirrors MapPicker.tsx's fitBounds(..., { padding: 48 }).
const REVEAL_FIT_FRACTION = 0.7

// Plain DOM (unlike MapPicker.tsx's canvas-rendered MapLibre markers), so these can reference the
// shared CSS custom properties directly instead of computing per-theme hex in JS - `.dark` on
// <html> resolves the guess marker's color automatically. Matches MapPicker's
// GUESS_MARKER_COLOR/ACTUAL_MARKER_COLOR.
const GUESS_MARKER_COLOR = "var(--color-primary)"
const ACTUAL_MARKER_COLOR = "#e11d48"

// The ruler is a full-width bar pinned to the bottom of the screen. Its height and the two derived
// bottom offsets live here together so a height change is a single edit, not a hunt across files -
// the pixel coupling CLAUDE.md warns about.
const RULER_HEIGHT_CLASS = "h-28 md:h-36"
// Exactly the ruler's own height (112/144px) - for anything that must stop flush against its top
// edge, with no gap (the asset photo wrapper: a gap there would show bare `--color-app-bg` through
// a sliver between the photo and the ruler instead of the photo running right up to it).
export const RULER_BOTTOM_CLASS = "bottom-28 md:bottom-36"
// Ruler height + a 12px breathing gap - for floating controls that sit just above the ruler
// (DateguessrGame's confirm button / result card), which do want visible space between them and it.
export const ABOVE_RULER_BOTTOM_CLASS = "bottom-[124px] md:bottom-[156px]"

interface TimelineRulerProps {
  selected: string | null // ISO date (yyyy-mm-dd)
  onSelectedChange: (iso: string) => void
  actual?: string | null // ISO date, only set once revealed
  disabled?: boolean
  // Hidden in the rounds-review screen - that ruler is permanently `disabled` as a
  // read-only replay, not mid-guess, so a control that changes its own zoom doesn't belong there.
  // Defaults to true so every live-play call site gets it for free.
  showZoomControls?: boolean
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function TimelineRuler({
  selected,
  onSelectedChange,
  actual = null,
  disabled = false,
  showZoomControls = true,
}: TimelineRulerProps) {
  const { t, i18n } = useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)

  const [containerWidth, setContainerWidth] = useState(() =>
    typeof window !== "undefined" ? window.innerWidth : 800,
  )
  const [pxPerDay, setPxPerDay] = useState(DEFAULT_PX_PER_DAY)
  const [centerDayIndex, setCenterDayIndex] = useState(() => todayDayIndex())

  // Start-of-gesture snapshots - captured in onDragStart/onPinchStart below, read in the matching
  // .../Move callback. usePointerGestures owns pointer capture/classification (drag vs. pinch,
  // capture, the pinch->drag restart transition); this component owns what a drag/pinch actually
  // does to pxPerDay/centerDayIndex - the 1D analog of AssetPhoto.tsx's 2D translate+scale.
  const dragStartCenterDayIndexRef = useRef(0)
  const pinchStartRef = useRef<{
    startDistance: number
    startPxPerDay: number
    anchorDayIndex: number
  } | null>(null)
  const revealAnimationFrameRef = useRef<number | null>(null)
  const zoomAnimationFrameRef = useRef<number | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width
      if (width) setContainerWidth(width)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useNonPassiveWheel(containerRef, (e) => {
    if (disabled) return
    e.preventDefault()

    // A trackpad's two-finger horizontal swipe arrives as deltaX on the same wheel event a mouse
    // wheel/pinch sends deltaY on - treat a deltaX-dominant event as panning the ruler sideways
    // instead of zooming, the same gesture MoreOrLess/Geoguessr's own scroll areas don't need
    // (this is the one game screen with genuine horizontal content to pan).
    if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
      setCenterDayIndex((prev) => prev + e.deltaX / pxPerDay)
      return
    }

    const rect = containerRef.current!.getBoundingClientRect()
    const cursorOffset = e.clientX - rect.left - rect.width / 2
    setPxPerDay((prevPxPerDay) => {
      const dayUnderCursor = centerDayIndex + cursorOffset / prevPxPerDay
      const factor = Math.exp(-e.deltaY * WHEEL_ZOOM_SENSITIVITY)
      const nextPxPerDay = clamp(prevPxPerDay * factor, MIN_PX_PER_DAY, MAX_PX_PER_DAY)
      setCenterDayIndex(dayUnderCursor - cursorOffset / nextPxPerDay)
      return nextPxPerDay
    })
  })

  function cancelRevealAnimation() {
    if (revealAnimationFrameRef.current !== null) {
      cancelAnimationFrame(revealAnimationFrameRef.current)
      revealAnimationFrameRef.current = null
    }
  }

  function cancelZoomAnimation() {
    if (zoomAnimationFrameRef.current !== null) {
      cancelAnimationFrame(zoomAnimationFrameRef.current)
      zoomAnimationFrameRef.current = null
    }
  }

  // Cleanup only - zoomBy (below) starts/restarts this animation itself on each button press, unlike
  // the reveal animation which is driven by its own effect further down.
  useEffect(() => cancelZoomAnimation, [])

  // Once the actual date is revealed, smoothly pan/zoom so both the guess and actual markers are
  // visible - the ruler's equivalent of MapPicker.tsx's fitBounds() reveal animation.
  useEffect(() => {
    if (!actual || !selected || containerWidth === 0) return
    const guessDayIndex = dayIndexFromIso(selected)
    const actualDayIndex = dayIndexFromIso(actual)
    const spanDays = Math.max(Math.abs(actualDayIndex - guessDayIndex), 1)
    const targetPxPerDay = clamp(
      (containerWidth * REVEAL_FIT_FRACTION) / spanDays,
      MIN_PX_PER_DAY,
      MAX_PX_PER_DAY,
    )
    const targetCenterDayIndex = (guessDayIndex + actualDayIndex) / 2

    const startPxPerDay = pxPerDay
    const startCenterDayIndex = centerDayIndex
    const startTime = performance.now()

    cancelRevealAnimation()
    function step(now: number) {
      const t = clamp((now - startTime) / REVEAL_ANIMATION_MS, 0, 1)
      const eased = easeOutCubic(t)
      setPxPerDay(startPxPerDay + (targetPxPerDay - startPxPerDay) * eased)
      setCenterDayIndex(startCenterDayIndex + (targetCenterDayIndex - startCenterDayIndex) * eased)
      if (t < 1) revealAnimationFrameRef.current = requestAnimationFrame(step)
    }
    revealAnimationFrameRef.current = requestAnimationFrame(step)
    return cancelRevealAnimation
    // Deliberately depends only on [actual, selected, containerWidth] - it reads pxPerDay/
    // centerDayIndex just as the animation's start point, not to re-run on every tick the
    // animation itself produces.
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [actual, selected, containerWidth])

  function dayIndexToX(dayIndex: number): number {
    return rulerDayIndexToX(dayIndex, centerDayIndex, pxPerDay, containerWidth)
  }

  function xToDayIndex(x: number): number {
    return rulerXToDayIndex(x, centerDayIndex, pxPerDay, containerWidth)
  }

  // A button has no cursor/pinch position to anchor under, so it anchors on the selected marker (what
  // the player actually cares about keeping in view) if there is one, and the ruler's own center
  // otherwise - same "keep the anchor day at the same on-screen x" math as the wheel handler above,
  // just solved directly from a day index instead of a pixel cursor offset. Unlike the
  // gestures (which are already continuous, driven by the input device itself), a button press is a
  // single discrete jump, so it gets its own short eased animation - same requestAnimationFrame +
  // easeOutCubic shape as the reveal animation above, just a separate ref/duration since a zoom
  // press and a reveal can't happen at the same time (the buttons are `disabled` during reveal) but
  // keeping them independent avoids the two animations fighting over one shared ref if that ever
  // changes.
  function zoomBy(factor: number) {
    if (disabled) return
    const anchorDayIndex = selectedDayIndex ?? centerDayIndex
    const startPxPerDay = pxPerDay
    const startCenterDayIndex = centerDayIndex
    const targetPxPerDay = clamp(startPxPerDay * factor, MIN_PX_PER_DAY, MAX_PX_PER_DAY)
    const targetCenterDayIndex =
      anchorDayIndex - (anchorDayIndex - startCenterDayIndex) * (startPxPerDay / targetPxPerDay)
    const startTime = performance.now()

    cancelZoomAnimation()
    function step(now: number) {
      const t = clamp((now - startTime) / ZOOM_BUTTON_ANIMATION_MS, 0, 1)
      const eased = easeOutCubic(t)
      setPxPerDay(startPxPerDay + (targetPxPerDay - startPxPerDay) * eased)
      setCenterDayIndex(startCenterDayIndex + (targetCenterDayIndex - startCenterDayIndex) * eased)
      if (t < 1) zoomAnimationFrameRef.current = requestAnimationFrame(step)
    }
    zoomAnimationFrameRef.current = requestAnimationFrame(step)
  }

  const monthFormatter = useMemo(
    () => new Intl.DateTimeFormat(i18n.language, { month: "short", timeZone: "UTC" }),
    [i18n.language],
  )

  const ticks = useMemo<Tick[]>(
    () => buildTicks(pxPerDay, centerDayIndex, containerWidth, monthFormatter),
    [pxPerDay, centerDayIndex, containerWidth, monthFormatter],
  )

  const gesture = usePointerGestures({
    disabled,
    onDragStart: () => {
      dragStartCenterDayIndexRef.current = centerDayIndex
    },
    onDragMove: (point, startPoint) => {
      const dx = point.x - startPoint.x
      setCenterDayIndex(dragStartCenterDayIndexRef.current - dx / pxPerDay)
    },
    onDragEnd: (point, moved) => {
      if (moved >= CLICK_MOVEMENT_THRESHOLD_PX) return
      const rect = containerRef.current!.getBoundingClientRect()
      const dayIndex = Math.round(xToDayIndex(point.x - rect.left))
      onSelectedChange(isoFromDayIndex(dayIndex))
    },
    onPinchStart: (a, b) => {
      const distance = Math.max(Math.hypot(a.x - b.x, a.y - b.y), 1)
      const midX = (a.x + b.x) / 2
      const rect = containerRef.current!.getBoundingClientRect()
      pinchStartRef.current = {
        startDistance: distance,
        startPxPerDay: pxPerDay,
        anchorDayIndex: xToDayIndex(midX - rect.left),
      }
    },
    onPinchMove: (a, b) => {
      if (!pinchStartRef.current) return
      const distance = Math.max(Math.hypot(a.x - b.x, a.y - b.y), 1)
      const midX = (a.x + b.x) / 2
      const rect = containerRef.current!.getBoundingClientRect()
      const factor = distance / pinchStartRef.current.startDistance
      const nextPxPerDay = clamp(
        pinchStartRef.current.startPxPerDay * factor,
        MIN_PX_PER_DAY,
        MAX_PX_PER_DAY,
      )
      const midOffset = midX - rect.left - containerWidth / 2
      setPxPerDay(nextPxPerDay)
      setCenterDayIndex(pinchStartRef.current.anchorDayIndex - midOffset / nextPxPerDay)
    },
    onPinchEnd: () => {
      pinchStartRef.current = null
    },
  })

  const selectedDayIndex = selected ? dayIndexFromIso(selected) : null
  const actualDayIndex = actual ? dayIndexFromIso(actual) : null

  return (
    <>
      <div
        ref={containerRef}
        {...gesture}
        className={`fixed bottom-0 left-0 right-0 z-20 ${RULER_HEIGHT_CLASS} touch-none overflow-hidden border-t border-line bg-surface shadow-card select-none`}
      >
        <div className="relative h-full w-full">
          {ticks.map((tick) => (
            <div
              key={`${tick.kind}-${tick.dayIndex}`}
              className="pointer-events-none absolute bottom-0 flex flex-col items-center"
              style={{ left: tick.x }}
            >
              {tick.label && (
                <span
                  className={`absolute mb-1 -translate-x-1/2 whitespace-nowrap font-mono text-faint pointer-events-none ${
                    tick.kind === "year"
                      ? "text-xs font-bold text-body"
                      : tick.kind === "month"
                        ? "text-[11px]"
                        : "text-[9px]"
                  }`}
                  style={{ bottom: "100%" }}
                >
                  {tick.label}
                </span>
              )}
              <div
                className={`-translate-x-1/2 ${
                  tick.kind === "year"
                    ? "h-14 w-[1.5px] bg-line-strong md:h-20"
                    : tick.kind === "month"
                      ? "h-9 w-px bg-line-strong md:h-12"
                      : "h-4 w-px bg-line md:h-5"
                }`}
              />
            </div>
          ))}

          {selectedDayIndex !== null && (
            <div
              className="pointer-events-none absolute top-0 bottom-0 -translate-x-1/2"
              style={{ left: dayIndexToX(selectedDayIndex) }}
            >
              <div className="h-full w-0.5" style={{ backgroundColor: GUESS_MARKER_COLOR }} />
              <div
                className="absolute top-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rounded-full border-2 border-white shadow-card"
                style={{ backgroundColor: GUESS_MARKER_COLOR }}
              />
            </div>
          )}

          {actualDayIndex !== null && (
            <div
              className="pointer-events-none absolute top-0 bottom-0 -translate-x-1/2"
              style={{ left: dayIndexToX(actualDayIndex) }}
            >
              <div className="h-full w-0.5" style={{ backgroundColor: ACTUAL_MARKER_COLOR }} />
              <div
                className="absolute top-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rounded-full border-2 border-white shadow-card"
                style={{ backgroundColor: ACTUAL_MARKER_COLOR }}
              />
            </div>
          )}
        </div>
      </div>

      {showZoomControls && (
        // Own container, outside the ruler's pointer-capturing div
        // - a tap on these buttons never reaches the pointer-gesture handlers above at all, rather
        // than relying solely on their target-guard. Floats above the ruler, mirroring the confirm
        // button's own ABOVE_RULER_BOTTOM_CLASS positioning (DateguessrGame.tsx) but on the right
        // instead of the left, and sized like AssetCarousel's arrow buttons (h-11 w-11 - a real
        // touch target, not a scaled-down desktop control).
        <div
          className={`fixed ${ABOVE_RULER_BOTTOM_CLASS} right-[18px] z-30 flex gap-2 md:right-10`}
        >
          <button
            type="button"
            onClick={() => zoomBy(1 / ZOOM_BUTTON_FACTOR)}
            disabled={disabled}
            aria-label={t("dateguessr.zoomOut")}
            className="flex h-11 w-11 items-center justify-center rounded-full border border-line-strong bg-surface text-body shadow-card transition-colors hover:bg-hover-tint disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-surface"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.4"
              strokeLinecap="round"
            >
              <path d="M5 12h14" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => zoomBy(ZOOM_BUTTON_FACTOR)}
            disabled={disabled}
            aria-label={t("dateguessr.zoomIn")}
            className="flex h-11 w-11 items-center justify-center rounded-full border border-line-strong bg-surface text-body shadow-card transition-colors hover:bg-hover-tint disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-surface"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.4"
              strokeLinecap="round"
            >
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>
        </div>
      )}
    </>
  )
}
