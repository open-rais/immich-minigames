// @vitest-environment jsdom
import { describe, expect, it } from "vitest"
import { render, renderHook, screen } from "@testing-library/react"
import { useState } from "react"

// Sanity check for the opt-in jsdom environment: the per-file `@vitest-environment` comment
// above is the mechanism every hook test uses, and jest-dom's matchers are wired up by
// `src/test/setup.ts`.
describe("jsdom test harness", () => {
  it("renders a component into a simulated DOM", () => {
    render(<p>hello</p>)
    expect(screen.getByText("hello")).toBeInTheDocument()
  })

  it("runs hooks with renderHook", () => {
    const { result } = renderHook(() => useState(7))
    expect(result.current[0]).toBe(7)
  })
})
