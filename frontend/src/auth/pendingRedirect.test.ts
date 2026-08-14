import { beforeEach, describe, expect, it } from "vitest"
import { consumePendingRedirectFrom, setPendingRedirectFrom } from "./pendingRedirect"

// Module-level state, so every test starts by draining whatever a previous one may have left -
// otherwise the suite would depend on execution order (and `--sequence.shuffle` would expose it).
beforeEach(() => {
  consumePendingRedirectFrom()
})

describe("pendingRedirect", () => {
  it("returns nothing when no redirect was recorded", () => {
    expect(consumePendingRedirectFrom()).toBeNull()
  })

  it("hands back the recorded path", () => {
    setPendingRedirectFrom("/games/timeline")
    expect(consumePendingRedirectFrom()).toBe("/games/timeline")
  })

  it("consumes the path, so a second read comes back empty", () => {
    // The "consume" in the name: a stale redirect must not fire again on the next login.
    setPendingRedirectFrom("/profile")
    expect(consumePendingRedirectFrom()).toBe("/profile")
    expect(consumePendingRedirectFrom()).toBeNull()
  })

  it("keeps only the last recorded path", () => {
    setPendingRedirectFrom("/first")
    setPendingRedirectFrom("/second")
    expect(consumePendingRedirectFrom()).toBe("/second")
  })
})
