import { describe, expect, it } from "vitest"

import { pickTip, TIP_CHANCE, type TipContext } from "./tips"

const FULL: TipContext = { hasRoundsView: true, isDaily: true, canInstall: true }
const BARE: TipContext = { hasRoundsView: false, isDaily: false, canInstall: false }

/** Feeds `pickTip` an exact sequence of "random" values, first the roll then the pick. */
function rolls(...values: number[]) {
  let i = 0
  return () => values[i++]
}

describe("pickTip", () => {
  it("shows nothing when the roll misses", () => {
    expect(pickTip(FULL, rolls(TIP_CHANCE))).toBeNull()
    expect(pickTip(FULL, rolls(0.99))).toBeNull()
  })

  it("shows a tip when the roll hits", () => {
    expect(pickTip(FULL, rolls(0, 0))).toBe("common.tips.report")
  })

  it("walks the whole bank as the second roll moves across it", () => {
    const keys = Array.from({ length: 7 }, (_, i) => pickTip(FULL, rolls(0, i / 7)))
    expect(keys).toEqual([
      "common.tips.report",
      "common.tips.leaderboard",
      "common.tips.relive",
      "common.tips.profileHistory",
      "common.tips.roundsImmich",
      "common.tips.install",
      "common.tips.dailyShare",
    ])
  })

  it("never picks past the end when the second roll returns almost 1", () => {
    expect(pickTip(FULL, rolls(0, 0.999999999))).toBe("common.tips.dailyShare")
  })

  it("drops the rounds-view tips when the mode has no rounds view", () => {
    const keys = new Set(
      Array.from({ length: 20 }, (_, i) => pickTip({ ...FULL, hasRoundsView: false }, rolls(0, i / 20))),
    )
    expect(keys).not.toContain("common.tips.report")
    expect(keys).not.toContain("common.tips.relive")
    expect(keys).not.toContain("common.tips.roundsImmich")
    expect(keys).toContain("common.tips.leaderboard")
  })

  it("drops the share tip outside daily games", () => {
    const keys = new Set(
      Array.from({ length: 20 }, (_, i) => pickTip({ ...FULL, isDaily: false }, rolls(0, i / 20))),
    )
    expect(keys).not.toContain("common.tips.dailyShare")
  })

  it("drops the install tip once the app is already installed", () => {
    const keys = new Set(
      Array.from({ length: 20 }, (_, i) => pickTip({ ...FULL, canInstall: false }, rolls(0, i / 20))),
    )
    expect(keys).not.toContain("common.tips.install")
  })

  it("still has context-free tips left when nothing else applies", () => {
    const keys = new Set(Array.from({ length: 20 }, (_, i) => pickTip(BARE, rolls(0, i / 20))))
    expect(keys).toEqual(new Set(["common.tips.leaderboard", "common.tips.profileHistory"]))
  })
})
