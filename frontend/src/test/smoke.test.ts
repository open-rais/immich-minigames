import { describe, expect, it } from "vitest"

// Sanity check for the default (node) environment: the runner resolves TS modules through the
// project's own vite config and vitest's API is importable without globals.
describe("test harness", () => {
  it("runs a test file in the node environment", () => {
    expect(1).toBe(1)
  })

  it("does not expose a DOM by default", () => {
    expect(typeof globalThis.document).toBe("undefined")
  })
})
