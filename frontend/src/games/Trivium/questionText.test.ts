import { describe, expect, it } from "vitest"

import { questionSegments } from "./questionText"

describe("questionSegments", () => {
  it("marks a single bold word", () => {
    expect(questionSegments("What **year** was it?")).toEqual([
      { word: "What", bold: false },
      { word: "year", bold: true },
      { word: "was", bold: false },
      { word: "it?", bold: false },
    ])
  })

  it("marks every word inside a multi-word span", () => {
    expect(questionSegments("Who is **Ana María?**")).toEqual([
      { word: "Who", bold: false },
      { word: "is", bold: false },
      { word: "Ana", bold: true },
      { word: "María?", bold: true },
    ])
  })

  it("returns everything unbold when there are no marks at all", () => {
    expect(questionSegments("Plain question?")).toEqual([
      { word: "Plain", bold: false },
      { word: "question?", bold: false },
    ])
  })

  it("handles a mark at the very start of the string", () => {
    expect(questionSegments("**Bold** then plain")).toEqual([
      { word: "Bold", bold: true },
      { word: "then", bold: false },
      { word: "plain", bold: false },
    ])
  })

  it("handles a mark at the very end of the string", () => {
    expect(questionSegments("Plain then **bold**")).toEqual([
      { word: "Plain", bold: false },
      { word: "then", bold: false },
      { word: "bold", bold: true },
    ])
  })
})
