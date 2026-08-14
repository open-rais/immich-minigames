import { describe, expect, it } from "vitest"
import { BOX_EXPAND_RATIO, MIN_BOX_PX, boxStyle, expandedBox } from "./faceBoxMath"

// A 100x200 detection box at (50,50) inside an 800x400 image. Picked so that every percentage
// boxStyle derives from it lands on an exactly representable value (4.375 / 5 / 16.25 / 65) - with
// rounder-looking inputs the emitted CSS reads "7.000000000000001%", which is valid but makes the
// string assertions below unreadable.
function face(overrides: Partial<Parameters<typeof expandedBox>[0]> = {}) {
  return {
    bounding_box_x1: 50,
    bounding_box_y1: 50,
    bounding_box_x2: 150,
    bounding_box_y2: 250,
    image_width: 800,
    image_height: 400,
    ...overrides,
  }
}

describe("expandedBox", () => {
  it("grows each side by the expand ratio of the box's own width and height", () => {
    const box = expandedBox(face())
    const padX = 100 * BOX_EXPAND_RATIO
    const padY = 200 * BOX_EXPAND_RATIO
    expect(box).toEqual({ x1: 50 - padX, y1: 50 - padY, x2: 150 + padX, y2: 250 + padY })
  })

  it("scales the padding per axis, so a wide box is not padded like a tall one", () => {
    const box = expandedBox(face())
    expect(box.x2 - box.x1).toBeCloseTo(100 * (1 + 2 * BOX_EXPAND_RATIO), 10)
    expect(box.y2 - box.y1).toBeCloseTo(200 * (1 + 2 * BOX_EXPAND_RATIO), 10)
  })

  it("never produces negative coordinates for a face against the top-left edge", () => {
    const box = expandedBox(face({ bounding_box_x1: 0, bounding_box_y1: 0 }))
    expect(box.x1).toBe(0)
    expect(box.y1).toBe(0)
  })

  it("never runs past the image for a face against the bottom-right edge", () => {
    const box = expandedBox(face({ bounding_box_x2: 800, bounding_box_y2: 400 }))
    expect(box.x2).toBe(800)
    expect(box.y2).toBe(400)
  })

  it("clamps both ends at once for a face that fills the whole image", () => {
    const box = expandedBox(
      face({
        bounding_box_x1: 0,
        bounding_box_y1: 0,
        bounding_box_x2: 800,
        bounding_box_y2: 400,
      }),
    )
    expect(box).toEqual({ x1: 0, y1: 0, x2: 800, y2: 400 })
  })
})

describe("boxStyle", () => {
  it("emits the exact calc() contract the CSS depends on", () => {
    // MIN_BOX_PX is interpolated rather than hardcoded so retuning the touch-target floor doesn't
    // fail this test - the shape of the expression is what's pinned here, not that number.
    expect(boxStyle(face())).toEqual({
      "--box-w": `max(16.25%, ${MIN_BOX_PX}px)`,
      "--box-h": `max(65%, ${MIN_BOX_PX}px)`,
      width: "var(--box-w)",
      height: "var(--box-h)",
      left: "calc(4.375% - (var(--box-w) - 16.25%) / 2)",
      top: "calc(5% - (var(--box-h) - 65%) / 2)",
    })
  })

  it("reuses the --box-w/--box-h custom properties in the offset calc()s", () => {
    // The whole reason those custom properties exist: left/top must resolve the same max() that
    // width/height do, instead of repeating the expression and drifting from it.
    const style = boxStyle(face()) as Record<string, string>
    expect(style.left).toContain("var(--box-w)")
    expect(style.top).toContain("var(--box-h)")
    expect(style.left).not.toContain("max(")
    expect(style.top).not.toContain("max(")
  })

  it("measures percentages against the detection resolution, not a fixed one", () => {
    // Same pixel box, image reported at half the width: every horizontal percentage doubles, and
    // the vertical axis is untouched.
    const wide = boxStyle(face()) as Record<string, string>
    const narrow = boxStyle(face({ image_width: 400 })) as Record<string, string>
    expect(wide["--box-w"]).toBe(`max(16.25%, ${MIN_BOX_PX}px)`)
    expect(narrow["--box-w"]).toBe(`max(32.5%, ${MIN_BOX_PX}px)`)
    expect(narrow.left).toBe("calc(8.75% - (var(--box-w) - 32.5%) / 2)")
    expect(narrow["--box-h"]).toBe(wide["--box-h"])
    expect(narrow.top).toBe(wide.top)
  })
})
