import { describe, expect, it } from "vitest"
import { buildTicks, dayIndexToX, easeOutCubic, lodTierFor, xToDayIndex } from "./rulerMath"
import { dayIndexOf } from "./timeMath"

// UTC-pinned so the month labels don't depend on the machine's timezone (the tick dates are day
// indices, which are UTC-based by construction - see timeMath.ts).
const monthFormatter = new Intl.DateTimeFormat("en", { month: "short", timeZone: "UTC" })

const CENTER = dayIndexOf(2024, 5, 15)

// The window buildTicks derives internally (lines 56-58), reproduced here so tests can assert
// against it without exporting it.
function windowFor(pxPerDay: number, containerWidth: number) {
  const halfWidthDays = containerWidth / 2 / pxPerDay
  return {
    min: Math.floor(CENTER - halfWidthDays) - 1,
    max: Math.ceil(CENTER + halfWidthDays) + 1,
  }
}

describe("lodTierFor", () => {
  it("switches tier exactly at the thresholds, not one step off", () => {
    expect(lodTierFor(0)).toBe("year")
    expect(lodTierFor(0.29)).toBe("year")
    expect(lodTierFor(0.3)).toBe("month") // threshold is inclusive on the month side
    expect(lodTierFor(2.79)).toBe("month")
    expect(lodTierFor(2.8)).toBe("day") // ...and on the day side
    expect(lodTierFor(60)).toBe("day")
  })
})

describe("projection", () => {
  it("round-trips a day index through x and back", () => {
    for (const pxPerDay of [0.02, 0.3, 2.8, 12, 60]) {
      const x = dayIndexToX(CENTER + 37, CENTER, pxPerDay, 800)
      expect(xToDayIndex(x, CENTER, pxPerDay, 800)).toBeCloseTo(CENTER + 37, 6)
    }
  })

  it("projects the centered day onto the middle of the container", () => {
    expect(dayIndexToX(CENTER, CENTER, 3, 800)).toBe(400)
    expect(xToDayIndex(400, CENTER, 3, 800)).toBe(CENTER)
  })
})

describe("buildTicks", () => {
  it("returns nothing for a zero-width container instead of dividing by zero", () => {
    const ticks = buildTicks(3, CENTER, 0, monthFormatter)
    expect(ticks).toEqual([])
  })

  it("emits only year ticks in the year tier", () => {
    const ticks = buildTicks(0.2, CENTER, 1000, monthFormatter)
    expect(ticks.length).toBeGreaterThan(0)
    expect(ticks.every((t) => t.kind === "year")).toBe(true)
  })

  it("emits years and months but no days in the month tier", () => {
    const ticks = buildTicks(1, CENTER, 1000, monthFormatter)
    expect(ticks.some((t) => t.kind === "month")).toBe(true)
    expect(ticks.some((t) => t.kind === "day")).toBe(false)
  })

  it("never emits a day tick on the 1st, which the month/year tick already covers", () => {
    const ticks = buildTicks(4, CENTER, 1000, monthFormatter)
    const days = ticks.filter((t) => t.kind === "day")
    expect(days.length).toBeGreaterThan(0)
    expect(days.some((t) => new Date(t.dayIndex * 86_400_000).getUTCDate() === 1)).toBe(false)
  })

  it("keeps month and day ticks inside the visible window", () => {
    const { min, max } = windowFor(4, 1000)
    const ticks = buildTicks(4, CENTER, 1000, monthFormatter)
    for (const tick of ticks.filter((t) => t.kind !== "year")) {
      expect(tick.dayIndex).toBeGreaterThanOrEqual(min)
      expect(tick.dayIndex).toBeLessThanOrEqual(max)
    }
  })

  it("emits the first visible year's January tick even when it falls before the window", () => {
    // Deliberate documentation of current behaviour, not an endorsement: the year loop pushes a
    // Jan-1 tick per year in range without the window check the month/day loops apply, so a window
    // that starts mid-year gets one extra tick. It lands at a negative x (off-screen), which is why
    // it has never been visible. If the year loop ever grows a window guard, this test is the one
    // that should be updated.
    const { min } = windowFor(3, 1000)
    const ticks = buildTicks(3, CENTER, 1000, monthFormatter)
    const january = ticks.find((t) => t.kind === "year" && t.dayIndex < min)
    expect(january).toBeDefined()
    expect(january!.x).toBeLessThan(0)
  })

  it("places every tick at the x its own day index projects to", () => {
    const ticks = buildTicks(3, CENTER, 1000, monthFormatter)
    for (const tick of ticks) {
      expect(tick.x).toBeCloseTo(dayIndexToX(tick.dayIndex, CENTER, 3, 1000), 6)
    }
  })

  it("thins labels out as the ruler zooms out over a fixed span of days", () => {
    // Container width is scaled with the zoom so the same ~400 days stay visible at every step -
    // otherwise the raw label count would grow again at low zoom simply because more years fit on
    // screen. What's being pinned is the label *frequency* tables, not the tick count.
    const VISIBLE_DAYS = 400
    const zooms = [60, 30, 15, 10, 5, 3, 2.8, 2, 1, 0.5, 0.3, 0.29, 0.1, 0.05, 0.02]
    const counts = zooms.map(
      (pxPerDay) =>
        buildTicks(pxPerDay, CENTER, pxPerDay * VISIBLE_DAYS, monthFormatter).filter(
          (t) => t.label !== null,
        ).length,
    )
    for (let i = 1; i < counts.length; i++) {
      expect(counts[i]).toBeLessThanOrEqual(counts[i - 1])
    }
    // Sanity floor/ceiling, so a change that flattens every count to 0 still fails the test above.
    expect(counts[0]).toBeGreaterThan(counts[counts.length - 1])
    expect(counts[counts.length - 1]).toBeGreaterThan(0)
  })
})

describe("easeOutCubic", () => {
  it("is pinned at both ends", () => {
    expect(easeOutCubic(0)).toBe(0)
    expect(easeOutCubic(1)).toBe(1)
  })

  it("increases monotonically over [0, 1]", () => {
    let previous = easeOutCubic(0)
    for (let i = 1; i <= 100; i++) {
      const current = easeOutCubic(i / 100)
      expect(current).toBeGreaterThan(previous)
      previous = current
    }
  })

  it("decelerates - the first half covers more ground than the second", () => {
    expect(easeOutCubic(0.5)).toBeGreaterThan(0.5)
  })
})
