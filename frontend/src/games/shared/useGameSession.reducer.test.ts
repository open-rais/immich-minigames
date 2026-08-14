import { describe, expect, it } from "vitest"
import { sessionReducer } from "./useGameSession"

// Pure reducer, no DOM and no mocks - the cheapest part of the whole level-2 plan, and the one that
// holds the invariant 8dd8c10 introduced the reducer for.

const idle = { screen: "idle", hasCurrentGame: null } as const

describe("sessionReducer - hasCurrentGame", () => {
  it("accepts the write while the screen is idle", () => {
    expect(sessionReducer(idle, { type: "hasCurrentGame", value: true })).toEqual({
      screen: "idle",
      hasCurrentGame: true,
    })
  })

  it("refuses the write once any other screen is active", () => {
    // The whole point: a late idle-check response must not flip the flag under a game already in
    // progress. Every screen other than idle refuses it.
    for (const screen of ["playing", "finished", "error"] as const) {
      const state = { screen, hasCurrentGame: false }
      expect(sessionReducer(state, { type: "hasCurrentGame", value: true })).toBe(state)
    }
  })

  it("returns the very same object when it refuses, so React skips the re-render", () => {
    const state = { screen: "playing", hasCurrentGame: false } as const
    expect(sessionReducer(state, { type: "hasCurrentGame", value: null })).toBe(state)
  })
})

describe("sessionReducer - screen", () => {
  it("preserves hasCurrentGame when the action omits it", () => {
    expect(
      sessionReducer(
        { screen: "idle", hasCurrentGame: true },
        { type: "screen", screen: "playing" },
      ),
    ).toEqual({ screen: "playing", hasCurrentGame: true })
  })

  it("distinguishes an explicit null from an omitted value", () => {
    // `undefined` means "leave it alone", `null` means "set it back to unknown" - collapsing the
    // two (a plain `??`) would make the daily flow unable to reset the flag.
    expect(
      sessionReducer(
        { screen: "idle", hasCurrentGame: true },
        { type: "screen", screen: "playing", hasCurrentGame: null },
      ),
    ).toEqual({ screen: "playing", hasCurrentGame: null })
  })

  it("applies a screen change and a hasCurrentGame write in the same dispatch", () => {
    // Two separate dispatches would not work: the second one would find the screen no longer idle
    // and get dropped by the case above. This is what makes the daily "finished" transition atomic.
    expect(
      sessionReducer(idle, { type: "screen", screen: "finished", hasCurrentGame: false }),
    ).toEqual({ screen: "finished", hasCurrentGame: false })
  })

  it("can write hasCurrentGame while leaving the screen where it is", () => {
    expect(sessionReducer(idle, { type: "screen", screen: "idle", hasCurrentGame: false })).toEqual(
      { screen: "idle", hasCurrentGame: false },
    )
  })
})
