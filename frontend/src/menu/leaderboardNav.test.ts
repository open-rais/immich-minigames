import { describe, expect, it } from "vitest"

import type { CatalogGame } from "../games/catalog"
import {
  buildCategories,
  cycleIndex,
  DAILY_CATEGORY,
  leaderboardHref,
  resolveNav,
  withCurrentTarget,
} from "./leaderboardNav"

// A stand-in for GAME_CATALOG - the real one keeps growing, and these assertions are about the
// two rings' wrap-around behaviour, not about which games happen to be registered today.
const catalog = [
  {
    gameType: "moreOrLess",
    gameTitleKey: "moreOrLess.title",
    modes: [{ mode: "personAssets" }, { mode: "albumAssets" }],
  },
  {
    gameType: "geoguessr",
    gameTitleKey: "geoguessr.title",
    modes: [{ mode: "distanceBetweenGuess" }],
  },
] as unknown as CatalogGame[]

const dailyTargets = [
  { gameType: "moreOrLess", mode: "personAssets" },
  { gameType: "geoguessr", mode: "distanceBetweenGuess" },
]

describe("cycleIndex", () => {
  it("wraps forwards past the end", () => {
    expect(cycleIndex(3, 2, 1)).toBe(0)
  })

  it("wraps backwards past the start", () => {
    expect(cycleIndex(3, 0, -1)).toBe(2)
  })

  it("is a no-op on an empty ring", () => {
    expect(cycleIndex(0, 0, 1)).toBe(0)
  })
})

describe("buildCategories", () => {
  it("puts daily first, then the catalog in menu order", () => {
    const ids = buildCategories(dailyTargets, catalog).map((c) => c.id)
    expect(ids).toEqual([DAILY_CATEGORY, "moreOrLess", "geoguessr"])
  })

  it("omits daily entirely when no mode is in the rotation", () => {
    const ids = buildCategories([], catalog).map((c) => c.id)
    expect(ids).toEqual(["moreOrLess", "geoguessr"])
  })
})

describe("withCurrentTarget", () => {
  it("keeps a target that is no longer in the rotation navigable", () => {
    const current = { gameType: "timeline", mode: "arcade" }
    expect(withCurrentTarget(dailyTargets, current)).toEqual([...dailyTargets, current])
  })

  it("leaves the list untouched when the target is already in it", () => {
    expect(withCurrentTarget(dailyTargets, dailyTargets[0])).toBe(dailyTargets)
  })
})

describe("leaderboardHref", () => {
  it("prefixes daily boards and carries their date", () => {
    expect(
      leaderboardHref(DAILY_CATEGORY, { gameType: "timeline", mode: "arcade" }, "?date=2026-08-20"),
    ).toBe("/daily/timeline/arcade/leaderboard?date=2026-08-20")
  })

  it("never puts a date on a normal board", () => {
    expect(
      leaderboardHref("timeline", { gameType: "timeline", mode: "arcade" }, "?date=2026-08-20"),
    ).toBe("/timeline/arcade/leaderboard")
  })
})

describe("resolveNav", () => {
  const categories = buildCategories(dailyTargets, catalog)

  it("wraps the mode ring inside its own category", () => {
    const nav = resolveNav(
      categories,
      "moreOrLess",
      { gameType: "moreOrLess", mode: "albumAssets" },
      "",
    )
    expect(nav?.nextModeHref).toBe("/moreOrLess/personAssets/leaderboard")
    expect(nav?.prevModeHref).toBe("/moreOrLess/personAssets/leaderboard")
  })

  it("wraps the category ring from the last game back to daily", () => {
    const nav = resolveNav(
      categories,
      "geoguessr",
      { gameType: "geoguessr", mode: "distanceBetweenGuess" },
      "",
    )
    expect(nav?.nextCategoryHref).toBe("/daily/moreOrLess/personAssets/leaderboard")
  })

  it("lands on the destination category's first mode", () => {
    const nav = resolveNav(
      categories,
      DAILY_CATEGORY,
      { gameType: "geoguessr", mode: "distanceBetweenGuess" },
      "",
    )
    expect(nav?.nextCategoryHref).toBe("/moreOrLess/personAssets/leaderboard")
  })

  it("carries the chosen date only while staying inside daily", () => {
    const nav = resolveNav(
      categories,
      DAILY_CATEGORY,
      { gameType: "moreOrLess", mode: "personAssets" },
      "?date=2026-08-20",
    )
    expect(nav?.nextModeHref).toBe(
      "/daily/geoguessr/distanceBetweenGuess/leaderboard?date=2026-08-20",
    )
    expect(nav?.nextCategoryHref).toBe("/moreOrLess/personAssets/leaderboard")
  })

  it("only names the game in the mode row for the daily category", () => {
    expect(resolveNav(categories, DAILY_CATEGORY, dailyTargets[0], "")?.showGameInModeLabel).toBe(
      true,
    )
    expect(
      resolveNav(categories, "moreOrLess", { gameType: "moreOrLess", mode: "personAssets" }, "")
        ?.showGameInModeLabel,
    ).toBe(false)
  })

  it("gives up when the current board is not in the ring", () => {
    expect(resolveNav(categories, "moreOrLess", { gameType: "moreOrLess", mode: "nope" }, "")).toBe(
      null,
    )
  })
})
