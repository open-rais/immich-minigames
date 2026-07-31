import { dateFromDayIndex, dayIndexOf } from "./timeMath"

// LOD thresholds (pixels-per-day) - first pass, meant to be tuned once this is actually on screen.
// Below YEAR_TIER_MAX: only year ticks. Below MONTH_TIER_MAX: years + months. Above that: also days.
const YEAR_TIER_MAX_PX_PER_DAY = 0.3
const MONTH_TIER_MAX_PX_PER_DAY = 2.8

export type LodTier = "year" | "month" | "day"

export interface Tick {
  dayIndex: number
  x: number
  kind: "year" | "month" | "day"
  label: string | null
}

export function lodTierFor(pxPerDay: number): LodTier {
  if (pxPerDay < YEAR_TIER_MAX_PX_PER_DAY) return "year"
  if (pxPerDay < MONTH_TIER_MAX_PX_PER_DAY) return "month"
  return "day"
}

export function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

export function dayIndexToX(
  dayIndex: number,
  centerDayIndex: number,
  pxPerDay: number,
  containerWidth: number,
): number {
  return containerWidth / 2 + (dayIndex - centerDayIndex) * pxPerDay
}

export function xToDayIndex(
  x: number,
  centerDayIndex: number,
  pxPerDay: number,
  containerWidth: number,
): number {
  return centerDayIndex + (x - containerWidth / 2) / pxPerDay
}

// The ruler's own tick set for the current zoom/pan state - year/month/day marks with a label
// frequency that thins out as pxPerDay drops, so labels never overlap. Pure aside from
// monthFormatter (an Intl.DateTimeFormat instance, itself pure per locale).
export function buildTicks(
  pxPerDay: number,
  centerDayIndex: number,
  containerWidth: number,
  monthFormatter: Intl.DateTimeFormat,
): Tick[] {
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
  const x = (dayIndex: number) => dayIndexToX(dayIndex, centerDayIndex, pxPerDay, containerWidth)

  // Dynamic label frequency based on zoom level to avoid overlap
  let yearLabelInterval = 5 // default: every 5 years
  if (pxPerDay >= 0.1)
    yearLabelInterval = 1 // show every year
  else if (pxPerDay >= 0.05)
    yearLabelInterval = 2 // every 2 years
  else if (pxPerDay >= 0.02) yearLabelInterval = 5 // every 5 years

  let monthLabelInterval = 12 // default: no months (only years)
  if (pxPerDay >= 3)
    monthLabelInterval = 1 // show every month
  else if (pxPerDay >= 2)
    monthLabelInterval = 2 // every 2 months
  else if (pxPerDay >= 1)
    monthLabelInterval = 3 // every 3 months
  else if (pxPerDay >= 0.3) monthLabelInterval = 6 // every 6 months

  let dayLabelInterval = 14 // default: every 2 weeks
  if (pxPerDay >= 30)
    dayLabelInterval = 1 // show every day
  else if (pxPerDay >= 15)
    dayLabelInterval = 3 // every 3 days
  else if (pxPerDay >= 10)
    dayLabelInterval = 7 // every week
  else if (pxPerDay >= 5) dayLabelInterval = 14 // every 2 weeks

  for (let year = minYear; year <= maxYear; year++) {
    const yearDayIndex = dayIndexOf(year, 0, 1)
    result.push({
      dayIndex: yearDayIndex,
      x: x(yearDayIndex),
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
        x: x(monthDayIndex),
        kind: "month",
        label:
          month % monthLabelInterval === 0
            ? monthFormatter.format(dateFromDayIndex(monthDayIndex))
            : null,
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
        x: x(dayIndex),
        kind: "day",
        label:
          dayLabelInterval === 1 || dayOfMonth % dayLabelInterval === 1 ? String(dayOfMonth) : null,
      })
    }
  }

  return result
}
