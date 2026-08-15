import { describe, expect, it } from "vitest"
import { boxStyle, expandedBox } from "./faceBoxMath"

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
  it("grows each side by half the growth factor's excess, of the box's own width and height", () => {
    const box = expandedBox(face(), 1.3)
    const padX = 100 * 0.15
    const padY = 200 * 0.15
    // toBeCloseTo, not toEqual - (1.3 - 1) / 2 isn't exactly representable in IEEE754, same reason
    // boxStyle's own comment already accepts a long-tail percentage string for non-round factors.
    expect(box.x1).toBeCloseTo(50 - padX, 10)
    expect(box.y1).toBeCloseTo(50 - padY, 10)
    expect(box.x2).toBeCloseTo(150 + padX, 10)
    expect(box.y2).toBeCloseTo(250 + padY, 10)
  })

  it("scales the padding per axis, so a wide box is not padded like a tall one", () => {
    const box = expandedBox(face(), 1.3)
    expect(box.x2 - box.x1).toBeCloseTo(100 * 1.3, 10)
    expect(box.y2 - box.y1).toBeCloseTo(200 * 1.3, 10)
  })

  it("at 1.0, reproduces the raw detection box exactly - no padding at all", () => {
    const box = expandedBox(face(), 1.0)
    expect(box).toEqual({ x1: 50, y1: 50, x2: 150, y2: 250 })
  })

  it("at 1.5, grows each side to the top of the admin-configurable range", () => {
    const box = expandedBox(face(), 1.5)
    expect(box.x2 - box.x1).toBeCloseTo(100 * 1.5, 10)
    expect(box.y2 - box.y1).toBeCloseTo(200 * 1.5, 10)
  })

  it("never produces negative coordinates for a face against the top-left edge", () => {
    const box = expandedBox(face({ bounding_box_x1: 0, bounding_box_y1: 0 }), 1.3)
    expect(box.x1).toBe(0)
    expect(box.y1).toBe(0)
  })

  it("never runs past the image for a face against the bottom-right edge", () => {
    const box = expandedBox(face({ bounding_box_x2: 800, bounding_box_y2: 400 }), 1.3)
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
      1.3,
    )
    expect(box).toEqual({ x1: 0, y1: 0, x2: 800, y2: 400 })
  })
})

describe("boxStyle", () => {
  it("emits plain percentages with no pixel floor", () => {
    // parseFloat, not a string toEqual - (1.3 - 1) / 2 isn't exactly representable in IEEE754 (see
    // expandedBox's own test above), so the emitted string can carry a long float tail here.
    const style = boxStyle(face(), 1.3) as Record<string, string>
    expect(parseFloat(style.left)).toBeCloseTo(4.375, 10)
    expect(parseFloat(style.top)).toBeCloseTo(5, 10)
    expect(parseFloat(style.width)).toBeCloseTo(16.25, 10)
    expect(parseFloat(style.height)).toBeCloseTo(65, 10)
  })

  it("at 1.0, the box exactly matches the detection box - no growth applied", () => {
    expect(boxStyle(face(), 1.0)).toEqual({
      left: "6.25%",
      top: "12.5%",
      width: "12.5%",
      height: "50%",
    })
  })

  it("at 1.5, grows to the top of the admin-configurable range", () => {
    expect(boxStyle(face(), 1.5)).toEqual({
      left: "3.125%",
      top: "0%",
      width: "18.75%",
      height: "75%",
    })
  })

  it("measures percentages against the detection resolution, not a fixed one", () => {
    // Same pixel box, image reported at half the width: every horizontal percentage doubles, and
    // the vertical axis is untouched.
    const wide = boxStyle(face(), 1.3)
    const narrow = boxStyle(face({ image_width: 400 }), 1.3)
    expect(narrow.width).toBe("32.5%")
    expect(narrow.left).toBe("8.75%")
    expect(narrow.height).toBe(wide.height)
    expect(narrow.top).toBe(wide.top)
  })
})
