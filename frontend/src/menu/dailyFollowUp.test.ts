import { describe, expect, it } from "vitest"

import type { DailyModeStatusOut, DailyStatusOut } from "../api/types/daily"
import type { CatalogGame } from "../games/catalog"
import { pendingDailyModes } from "./dailyFollowUp"

// A stand-in for GAME_CATALOG, same reasoning as menu/leaderboardNav.test.ts: these assertions are
// about which statuses count as pending, not about which games are registered today.
const catalog = [
  {
    gameType: "moreOrLess",
    gameTitleKey: "moreOrLess.title",
    modes: [
      { mode: "personAssets", modeTitleKey: "moreOrLess.modes.personAssets" },
      { mode: "albumAssets", modeTitleKey: "moreOrLess.modes.albumAssets" },
    ],
  },
  {
    gameType: "geoguessr",
    gameTitleKey: "geoguessr.title",
    modes: [{ mode: "distanceBetweenGuess", modeTitleKey: "geoguessr.modes.distanceBetweenGuess" }],
  },
] as unknown as CatalogGame[]

function modeStatus(overrides: Partial<DailyModeStatusOut> = {}): DailyModeStatusOut {
  return {
    game_type: "moreOrLess",
    mode: "personAssets",
    status: "not_played",
    game_id: null,
    score: null,
    ...overrides,
  }
}

function status(modes: DailyModeStatusOut[]): DailyStatusOut {
  return { resets_at: "2026-08-24T00:00:00Z", server_now: "2026-08-23T10:00:00Z", modes }
}

describe("pendingDailyModes", () => {
  it("keeps the modes that haven't been played and the ones left mid-game", () => {
    const pending = pendingDailyModes(
      status([
        modeStatus({ status: "finished", game_id: "g1", score: 10 }),
        modeStatus({ mode: "albumAssets", status: "in_progress", game_id: "g2" }),
        modeStatus({ game_type: "geoguessr", mode: "distanceBetweenGuess" }),
      ]),
      catalog,
    )

    expect(pending.map((p) => `${p.status.game_type}:${p.status.mode}`)).toEqual([
      "moreOrLess:albumAssets",
      "geoguessr:distanceBetweenGuess",
    ])
  })

  it("resolves each pending mode's catalog entry", () => {
    const [pending] = pendingDailyModes(status([modeStatus()]), catalog)

    expect(pending.game.gameTitleKey).toBe("moreOrLess.title")
    expect(pending.mode.modeTitleKey).toBe("moreOrLess.modes.personAssets")
  })

  it("drops a rotation mode this build's catalog doesn't know", () => {
    expect(
      pendingDailyModes(status([modeStatus({ game_type: "unknownGame", mode: "x" })]), catalog),
    ).toEqual([])
  })

  it("is empty when every mode is finished, and when there is no status at all", () => {
    expect(pendingDailyModes(status([modeStatus({ status: "finished" })]), catalog)).toEqual([])
    expect(pendingDailyModes(undefined, catalog)).toEqual([])
  })
})
