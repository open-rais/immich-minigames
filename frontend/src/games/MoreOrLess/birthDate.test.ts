import { afterEach, describe, expect, it, vi } from "vitest"
import { formatBirthDate } from "./birthDate"

afterEach(() => {
  vi.unstubAllEnvs()
})

describe("formatBirthDate", () => {
  it("does not slip to the previous day in a timezone behind UTC", () => {
    // The regression the module's own comment describes: new Date("1990-01-01") is UTC midnight,
    // so formatting it in local time would render Dec 31, 1989 anywhere west of Greenwich.
    vi.stubEnv("TZ", "Pacific/Midway") // UTC-11
    const formatted = formatBirthDate("1990-01-01", "en")
    expect(formatted).toContain("1990")
    expect(formatted).not.toContain("1989")
    expect(formatted).toBe("Jan 1, 1990")
  })

  it("does not slip to the next day in a timezone ahead of UTC", () => {
    vi.stubEnv("TZ", "Pacific/Kiritimati") // UTC+14
    expect(formatBirthDate("1990-12-31", "en")).toBe("Dec 31, 1990")
  })

  it("renders the same date regardless of the machine timezone", () => {
    vi.stubEnv("TZ", "Pacific/Midway")
    const west = formatBirthDate("1815-12-10", "en")
    vi.stubEnv("TZ", "Pacific/Kiritimati")
    const east = formatBirthDate("1815-12-10", "en")
    expect(west).toBe(east)
  })

  it("actually uses the language it is given", () => {
    // Exact Spanish copy isn't asserted (it's ICU's, and it moves between Node versions) - what
    // matters is that `language` reaches Intl instead of being ignored.
    const en = formatBirthDate("2024-07-15", "en")
    const es = formatBirthDate("2024-07-15", "es")
    expect(es).not.toBe(en)
    expect(es).toContain("2024")
    expect(es).toContain("15")
  })
})
