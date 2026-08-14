import { describe, expect, it } from "vitest"
import { fitBox } from "./fitBox"

describe("fitBox", () => {
  it("letterboxes above and below when the image is wider than the container", () => {
    const box = fitBox({ width: 400, height: 100 }, { width: 400, height: 400 })
    expect(box).toEqual({ left: 0, top: 150, width: 400, height: 100 })
  })

  it("letterboxes left and right when the image is taller than the container", () => {
    const box = fitBox({ width: 100, height: 400 }, { width: 400, height: 400 })
    expect(box).toEqual({ left: 150, top: 0, width: 100, height: 400 })
  })

  it("fills the container exactly when the aspect ratios match", () => {
    const box = fitBox({ width: 800, height: 400 }, { width: 400, height: 200 })
    expect(box).toEqual({ left: 0, top: 0, width: 400, height: 200 })
  })

  it("preserves the natural aspect ratio at any container size", () => {
    const natural = { width: 4032, height: 3024 }
    for (const container of [
      { width: 300, height: 900 },
      { width: 900, height: 300 },
      { width: 1000, height: 1000 },
      { width: 137, height: 401 },
    ]) {
      const box = fitBox(natural, container)
      expect(box.width / box.height).toBeCloseTo(natural.width / natural.height, 10)
    }
  })

  it("scales down to fit without ever overflowing the container", () => {
    const box = fitBox({ width: 4032, height: 3024 }, { width: 300, height: 900 })
    expect(box.width).toBeLessThanOrEqual(300)
    expect(box.height).toBeLessThanOrEqual(900)
    expect(box.left).toBeGreaterThanOrEqual(0)
    expect(box.top).toBeGreaterThanOrEqual(0)
  })

  it("scales up a small image to fill the constraining axis", () => {
    const box = fitBox({ width: 40, height: 30 }, { width: 400, height: 400 })
    expect(box.width).toBe(400)
    expect(box.height).toBe(300)
  })
})
