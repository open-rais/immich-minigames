import { useEffect, useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"

import { dateFromDayIndex, dayIndexFromIso, dayIndexOf, isoFromDayIndex, todayDayIndex } from "./timeMath"

// Zoom is expressed as pixels-per-day, the direct analog of MapPicker.tsx's MapLibre zoom level -
// same "zoom anchored under the cursor/pinch midpoint" UX principle, implemented by hand here since
// this is a custom ruler rather than a map library.
const MIN_PX_PER_DAY = 0.02 // ~80+ years visible across a typical viewport
const MAX_PX_PER_DAY = 60 // a single day comfortably fills a tap target
const DEFAULT_PX_PER_DAY = 2.2 // starting zoom - months visible, matches the "month" LOD tier

// LOD thresholds (pixels-per-day) - first pass, meant to be tuned once this is actually on screen.
// Below YEAR_TIER_MAX: only year ticks. Below MONTH_TIER_MAX: years + months. Above that: also days.
const YEAR_TIER_MAX_PX_PER_DAY = 0.3
const MONTH_TIER_MAX_PX_PER_DAY = 2.8

const WHEEL_ZOOM_SENSITIVITY = 0.0015
const CLICK_MOVEMENT_THRESHOLD_PX = 6
const REVEAL_ANIMATION_MS = 500
// After a reveal, the two markers should span roughly this fraction of the ruler's width once
// fitted - mirrors MapPicker.tsx's fitBounds(..., { padding: 48 }).
const REVEAL_FIT_FRACTION = 0.7

// Plain DOM (unlike MapPicker.tsx's canvas-rendered MapLibre markers), so these can reference the
// shared CSS custom properties directly instead of computing per-theme hex in JS - `.dark` on
// <html> resolves the guess marker's color automatically. Matches MapPicker's
// GUESS_MARKER_COLOR/ACTUAL_MARKER_COLOR.
const GUESS_MARKER_COLOR = "var(--color-primary)"
const ACTUAL_MARKER_COLOR = "#e11d48"

// The ruler is a full-width bar pinned to the bottom of the screen. Its height and the matching
// bottom offset for controls that sit just above it (DateguessrGame's confirm button / result card)
// live here together so a height change is a single edit, not a hunt across files - the pixel
// coupling CLAUDE.md warns about. Offset = ruler height (112/144px) + a 12px gap.
const RULER_HEIGHT_CLASS = "h-28 md:h-36"
export const ABOVE_RULER_BOTTOM_CLASS = "bottom-[124px] md:bottom-[156px]"

type LodTier = "year" | "month" | "day"

interface Tick {
  dayIndex: number
  x: number
  kind: "year" | "month" | "day"
  label: string | null
}

interface TimelineRulerProps {
  selected: string | null // ISO date (yyyy-mm-dd)
  onSelectedChange: (iso: string) => void
  actual?: string | null // ISO date, only set once revealed
  disabled?: boolean
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function lodTierFor(pxPerDay: number): LodTier {
  if (pxPerDay < YEAR_TIER_MAX_PX_PER_DAY) return "year"
  if (pxPerDay < MONTH_TIER_MAX_PX_PER_DAY) return "month"
  return "day"
}

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

export function TimelineRuler({ selected, onSelectedChange, actual = null, disabled = false }: TimelineRulerProps) {
  const { i18n } = useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)

  const [containerWidth, setContainerWidth] = useState(() => (typeof window !== "undefined" ? window.innerWidth : 800))
  const [pxPerDay, setPxPerDay] = useState(DEFAULT_PX_PER_DAY)
  const [centerDayIndex, setCenterDayIndex] = useState(() => todayDayIndex())

  // Gesture bookkeeping - refs, not state, since they track in-progress pointer interactions
  // rather than anything that should trigger a re-render on their own.
  const activePointersRef = useRef<Map<number, { x: number; y: number }>>(new Map())
  const dragRef = useRef<{ startClientX: number; startCenterDayIndex: number; moved: number } | null>(null)
  const pinchRef = useRef<{ startDistance: number; startPxPerDay: number; anchorDayIndex: number } | null>(null)
  const animationFrameRef = useRef<number | null>(null)
  // Mirrors centerDayIndex for the native (non-React) wheel listener below, which is only
  // re-attached when `disabled` changes and would otherwise close over a stale value.
  const centerDayIndexRef = useRef(centerDayIndex)
  centerDayIndexRef.current = centerDayIndex

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

  // React marks onWheel as a passive listener by default, so preventDefault() inside a JSX handler
  // silently does nothing (and warns) - attaching natively is the only way to actually stop the
  // page from scrolling while the player zooms the ruler.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    function handleWheel(e: WheelEvent) {
      if (disabled) return
      e.preventDefault()
      const rect = el!.getBoundingClientRect()
      const cursorOffset = e.clientX - rect.left - rect.width / 2
      setPxPerDay((prevPxPerDay) => {
        const dayUnderCursor = centerDayIndexRef.current + cursorOffset / prevPxPerDay
        const factor = Math.exp(-e.deltaY * WHEEL_ZOOM_SENSITIVITY)
        const nextPxPerDay = clamp(prevPxPerDay * factor, MIN_PX_PER_DAY, MAX_PX_PER_DAY)
        setCenterDayIndex(dayUnderCursor - cursorOffset / nextPxPerDay)
        return nextPxPerDay
      })
    }

    el.addEventListener("wheel", handleWheel, { passive: false })
    return () => el.removeEventListener("wheel", handleWheel)
  }, [disabled])

  function cancelRevealAnimation() {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }
  }

  // Once the actual date is revealed, smoothly pan/zoom so both the guess and actual markers are
  // visible - the ruler's equivalent of MapPicker.tsx's fitBounds() reveal animation.
  useEffect(() => {
    if (!actual || !selected || containerWidth === 0) return
    const guessDayIndex = dayIndexFromIso(selected)
    const actualDayIndex = dayIndexFromIso(actual)
    const spanDays = Math.max(Math.abs(actualDayIndex - guessDayIndex), 1)
    const targetPxPerDay = clamp((containerWidth * REVEAL_FIT_FRACTION) / spanDays, MIN_PX_PER_DAY, MAX_PX_PER_DAY)
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
      if (t < 1) animationFrameRef.current = requestAnimationFrame(step)
    }
    animationFrameRef.current = requestAnimationFrame(step)
    return cancelRevealAnimation
    // Deliberately depends only on [actual, selected, containerWidth] - it reads pxPerDay/
    // centerDayIndex just as the animation's start point, not to re-run on every tick the
    // animation itself produces.
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [actual, selected, containerWidth])

  function dayIndexToX(dayIndex: number): number {
    return containerWidth / 2 + (dayIndex - centerDayIndex) * pxPerDay
  }

  function xToDayIndex(x: number): number {
    return centerDayIndex + (x - containerWidth / 2) / pxPerDay
  }

  const monthFormatter = useMemo(
    () => new Intl.DateTimeFormat(i18n.language, { month: "short", timeZone: "UTC" }),
    [i18n.language],
  )

  const ticks = useMemo<Tick[]>(() => {
    if (containerWidth === 0) return []
    const tier = lodTierFor(pxPerDay)
    const halfWidthDays = containerWidth / 2 / pxPerDay
    const minDayIndex = Math.floor(centerDayIndex - halfWidthDays) - 1
    const maxDayIndex = Math.ceil(centerDayIndex + halfWidthDays) + 1
    const minDate = dateFromDayIndex(minDayIndex)
    const maxDate = dateFromDayIndex(maxDayIndex)
    const minYear = minDate.getUTCFullYear()
    const maxYear = maxDate.getUTCFullYear()

    const result: Tick[] = []

    // Dynamic label frequency based on zoom level to avoid overlap
    let yearLabelInterval = 5 // default: every 5 years
    if (pxPerDay >= 0.1) yearLabelInterval = 1 // show every year
    else if (pxPerDay >= 0.05) yearLabelInterval = 2 // every 2 years
    else if (pxPerDay >= 0.02) yearLabelInterval = 5 // every 5 years

    let monthLabelInterval = 12 // default: no months (only years)
    if (pxPerDay >= 3) monthLabelInterval = 1 // show every month
    else if (pxPerDay >= 2) monthLabelInterval = 2 // every 2 months
    else if (pxPerDay >= 1) monthLabelInterval = 3 // every 3 months
    else if (pxPerDay >= 0.3) monthLabelInterval = 6 // every 6 months

    let dayLabelInterval = 14 // default: every 2 weeks
    if (pxPerDay >= 30) dayLabelInterval = 1 // show every day
    else if (pxPerDay >= 15) dayLabelInterval = 3 // every 3 days
    else if (pxPerDay >= 10) dayLabelInterval = 7 // every week
    else if (pxPerDay >= 5) dayLabelInterval = 14 // every 2 weeks

    for (let year = minYear; year <= maxYear; year++) {
      const yearDayIndex = dayIndexOf(year, 0, 1)
      result.push({
        dayIndex: yearDayIndex,
        x: dayIndexToX(yearDayIndex),
        kind: "year",
        label: year % yearLabelInterval === 0 ? String(year) : null,
      })

      if (tier === "year") continue

      for (let month = 0; month < 12; month++) {
        if (month === 0) continue // already covered by the year tick above
        const monthDayIndex = dayIndexOf(year, month, 1)
        if (monthDayIndex < minDayIndex || monthDayIndex > maxDayIndex) continue
        result.push({
          dayIndex: monthDayIndex,
          x: dayIndexToX(monthDayIndex),
          kind: "month",
          label: month % monthLabelInterval === 0 ? monthFormatter.format(dateFromDayIndex(monthDayIndex)) : null,
        })
      }

      if (tier !== "day") continue

      const daysInYear = dayIndexOf(year + 1, 0, 1) - yearDayIndex
      for (let offset = 0; offset < daysInYear; offset++) {
        const dayIndex = yearDayIndex + offset
        if (dayIndex < minDayIndex || dayIndex > maxDayIndex) continue
        const dayOfMonth = dateFromDayIndex(dayIndex).getUTCDate()
        if (dayOfMonth === 1) continue // the 1st already has a month/year tick above
        result.push({
          dayIndex,
          x: dayIndexToX(dayIndex),
          kind: "day",
          label: dayLabelInterval === 1 || dayOfMonth % dayLabelInterval === 1 ? String(dayOfMonth) : null,
        })
      }
    }

    return result
    // dayIndexToX is a plain closure over this same render's pxPerDay/centerDayIndex/containerWidth
    // (all already listed below) - it isn't its own independent input, just recomputed alongside them.
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [pxPerDay, centerDayIndex, containerWidth, monthFormatter])

  function handlePointerDown(e: React.PointerEvent<HTMLDivElement>) {
    if (disabled) return
    e.currentTarget.setPointerCapture(e.pointerId)
    activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })

    if (activePointersRef.current.size === 1) {
      dragRef.current = { startClientX: e.clientX, startCenterDayIndex: centerDayIndex, moved: 0 }
      pinchRef.current = null
    } else if (activePointersRef.current.size === 2) {
      dragRef.current = null
      const [p1, p2] = [...activePointersRef.current.values()]
      const distance = Math.hypot(p1.x - p2.x, p1.y - p2.y)
      const midX = (p1.x + p2.x) / 2
      const rect = containerRef.current!.getBoundingClientRect()
      pinchRef.current = {
        startDistance: Math.max(distance, 1),
        startPxPerDay: pxPerDay,
        anchorDayIndex: xToDayIndex(midX - rect.left),
      }
    }
  }

  function handlePointerMove(e: React.PointerEvent) {
    if (disabled || !activePointersRef.current.has(e.pointerId)) return
    activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })

    if (activePointersRef.current.size >= 2 && pinchRef.current) {
      const [p1, p2] = [...activePointersRef.current.values()]
      const distance = Math.max(Math.hypot(p1.x - p2.x, p1.y - p2.y), 1)
      const midX = (p1.x + p2.x) / 2
      const rect = containerRef.current!.getBoundingClientRect()
      const factor = distance / pinchRef.current.startDistance
      const nextPxPerDay = clamp(pinchRef.current.startPxPerDay * factor, MIN_PX_PER_DAY, MAX_PX_PER_DAY)
      const midOffset = midX - rect.left - containerWidth / 2
      setPxPerDay(nextPxPerDay)
      setCenterDayIndex(pinchRef.current.anchorDayIndex - midOffset / nextPxPerDay)
      return
    }

    if (activePointersRef.current.size === 1 && dragRef.current) {
      const dx = e.clientX - dragRef.current.startClientX
      dragRef.current.moved = Math.max(dragRef.current.moved, Math.abs(dx))
      setCenterDayIndex(dragRef.current.startCenterDayIndex - dx / pxPerDay)
    }
  }

  function handlePointerUp(e: React.PointerEvent) {
    const wasTap = !disabled && activePointersRef.current.size === 1 && !!dragRef.current && dragRef.current.moved < CLICK_MOVEMENT_THRESHOLD_PX
    if (wasTap) {
      const rect = containerRef.current!.getBoundingClientRect()
      const dayIndex = Math.round(xToDayIndex(e.clientX - rect.left))
      onSelectedChange(isoFromDayIndex(dayIndex))
    }

    activePointersRef.current.delete(e.pointerId)
    if (activePointersRef.current.size < 2) pinchRef.current = null
    if (activePointersRef.current.size === 0) {
      dragRef.current = null
    } else if (activePointersRef.current.size === 1) {
      // One finger remains after a pinch ends - restart drag tracking from it, marked as already
      // "moved" so lifting that finger next doesn't misfire a tap.
      const [[, point]] = activePointersRef.current
      dragRef.current = { startClientX: point.x, startCenterDayIndex: centerDayIndex, moved: CLICK_MOVEMENT_THRESHOLD_PX }
    }
  }

  const selectedDayIndex = selected ? dayIndexFromIso(selected) : null
  const actualDayIndex = actual ? dayIndexFromIso(actual) : null

  return (
    <div
      ref={containerRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
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
                  tick.kind === "year" ? "text-xs font-bold text-body" : tick.kind === "month" ? "text-[11px]" : "text-[9px]"
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
  )
}
