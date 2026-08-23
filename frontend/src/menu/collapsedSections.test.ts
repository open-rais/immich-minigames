// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest"

import { isCollapsed, setCollapsed } from "./collapsedSections"

const STORAGE_KEY = "minigames-collapsed-sections"

beforeEach(() => {
  localStorage.clear()
})

describe("isCollapsed", () => {
  it("nothing is collapsed when the key is empty", () => {
    expect(isCollapsed("geoguessr")).toBe(false)
  })

  it("degrades to nothing-collapsed on corrupt JSON, without throwing", () => {
    localStorage.setItem(STORAGE_KEY, "{not valid json")
    expect(() => isCollapsed("geoguessr")).not.toThrow()
    expect(isCollapsed("geoguessr")).toBe(false)
  })

  it("degrades to nothing-collapsed when the stored value isn't an array", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ geoguessr: true }))
    expect(isCollapsed("geoguessr")).toBe(false)
  })
})

describe("setCollapsed", () => {
  it("round-trips through isCollapsed", () => {
    setCollapsed("geoguessr", true)
    expect(isCollapsed("geoguessr")).toBe(true)

    setCollapsed("geoguessr", false)
    expect(isCollapsed("geoguessr")).toBe(false)
  })

  it("collapsing one id doesn't affect another", () => {
    setCollapsed("geoguessr", true)
    setCollapsed("daily", true)
    setCollapsed("geoguessr", false)

    expect(isCollapsed("geoguessr")).toBe(false)
    expect(isCollapsed("daily")).toBe(true)
  })

  it("collapsing the same id twice doesn't duplicate it in storage", () => {
    setCollapsed("geoguessr", true)
    setCollapsed("geoguessr", true)

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]")
    expect(stored).toEqual(["geoguessr"])
  })
})
