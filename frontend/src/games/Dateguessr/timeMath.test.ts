import { afterEach, describe, expect, it, vi } from "vitest"
import {
  dateFromDayIndex,
  dayIndexFromIso,
  dayIndexOf,
  isoFromDayIndex,
  todayDayIndex,
} from "./timeMath"

// The whole point of this module is that a day index means the same calendar day no matter what
// timezone the machine running it is in, so several tests here drive the process timezone directly.
// Node re-reads TZ on every Date operation, so stubbing it mid-test is enough; vi.stubEnv is used
// instead of touching process.env by hand because the app's tsconfig has no node types.
function withTz(tz: string, fn: () => void) {
  vi.stubEnv("TZ", tz)
  fn()
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.useRealTimers()
})

describe("dayIndexOf / dateFromDayIndex", () => {
  it("round-trips every calendar date back to the same day index", () => {
    const dates: [number, number, number][] = [
      [1970, 0, 1], // the epoch itself - day 0
      [2024, 1, 29], // leap day
      [2023, 11, 31], // last day of a year
      [2024, 0, 1], // first day of a year
      [1999, 6, 15],
      [2100, 2, 1], // a non-leap century
    ]
    for (const [year, monthIndex, day] of dates) {
      const index = dayIndexOf(year, monthIndex, day)
      const date = dateFromDayIndex(index)
      expect(dayIndexOf(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate())).toBe(index)
    }
  })

  it("puts the epoch at day 0", () => {
    expect(dayIndexOf(1970, 0, 1)).toBe(0)
  })

  it("returns whole integers, never fractions", () => {
    expect(Number.isInteger(dayIndexOf(2024, 5, 15))).toBe(true)
    expect(Number.isInteger(dayIndexOf(1830, 11, 31))).toBe(true)
  })
})

describe("isoFromDayIndex / dayIndexFromIso", () => {
  it("round-trips ISO dates, including years below 1000 that need zero padding", () => {
    // Note: Date.UTC remaps years 0-99 onto 1900-1999, so this module can't represent them - 0500
    // and 0999 are the interesting cases for the padStart(4) without hitting that remapping.
    for (const iso of ["2024-02-29", "1970-01-01", "2023-12-31", "0500-01-01", "0999-12-31"]) {
      expect(isoFromDayIndex(dayIndexFromIso(iso))).toBe(iso)
    }
  })

  it("zero-pads month and day to two digits", () => {
    expect(isoFromDayIndex(dayIndexFromIso("2024-01-05"))).toBe("2024-01-05")
  })
})

describe("consecutive days", () => {
  it("differ by exactly one across month, leap-day and year boundaries", () => {
    const pairs: [string, string][] = [
      ["2024-02-28", "2024-02-29"], // into the leap day
      ["2024-02-29", "2024-03-01"], // out of it
      ["2023-02-28", "2023-03-01"], // same boundary on a non-leap year
      ["2023-12-31", "2024-01-01"], // year rollover
      ["2024-04-30", "2024-05-01"], // 30-day month
    ]
    for (const [before, after] of pairs) {
      expect(dayIndexFromIso(after) - dayIndexFromIso(before)).toBe(1)
    }
  })
})

describe("timezone independence", () => {
  // The regression this module's own header comment exists to prevent: the same calendar date
  // resolving to different day indices depending on where the player is.
  it("maps an ISO date to the same day index at UTC+14 and at UTC-11", () => {
    let atPlus14 = 0
    let atMinus11 = 0
    withTz("Pacific/Kiritimati", () => {
      atPlus14 = dayIndexFromIso("2024-03-15")
    })
    withTz("Pacific/Midway", () => {
      atMinus11 = dayIndexFromIso("2024-03-15")
    })
    expect(atPlus14).toBe(atMinus11)
    expect(atPlus14).toBe(dayIndexOf(2024, 2, 15))
  })

  it("renders a day index back to the same ISO date at UTC+14 and at UTC-11", () => {
    const index = dayIndexOf(2024, 2, 15)
    withTz("Pacific/Kiritimati", () => {
      expect(isoFromDayIndex(index)).toBe("2024-03-15")
    })
    withTz("Pacific/Midway", () => {
      expect(isoFromDayIndex(index)).toBe("2024-03-15")
    })
  })
})

describe("todayDayIndex", () => {
  it("follows the local calendar day, not the UTC one, just after local midnight", () => {
    // 11:00 UTC on the 15th is already 01:00 on the 16th in Kiritimati (UTC+14).
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2024-03-15T11:00:00Z"))
    withTz("Pacific/Kiritimati", () => {
      expect(todayDayIndex()).toBe(dayIndexOf(2024, 2, 16))
      expect(todayDayIndex()).not.toBe(dayIndexFromIso("2024-03-15"))
    })
  })

  it("follows the local calendar day, not the UTC one, just before local midnight", () => {
    // 05:00 UTC on the 16th is still 18:00 on the 15th in Midway (UTC-11).
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2024-03-16T05:00:00Z"))
    withTz("Pacific/Midway", () => {
      expect(todayDayIndex()).toBe(dayIndexOf(2024, 2, 15))
      expect(todayDayIndex()).not.toBe(dayIndexFromIso("2024-03-16"))
    })
  })
})
