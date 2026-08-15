import { describe, expect, it } from "vitest"
import {
  antimeridianSafeLngLats,
  effectiveMaxZoom,
  haversineDistanceMeters,
} from "./mapCameraMath"

describe("haversineDistanceMeters", () => {
  it("is zero for the same point", () => {
    expect(haversineDistanceMeters({ lat: 40.7128, lng: -74.006 }, { lat: 40.7128, lng: -74.006 })).toBe(0)
  })

  it("matches the well-known NYC-London great-circle distance (~5550-5580km)", () => {
    const nyc = { lat: 40.7128, lng: -74.006 }
    const london = { lat: 51.5074, lng: -0.1278 }
    const km = haversineDistanceMeters(nyc, london) / 1000
    expect(km).toBeGreaterThan(5550)
    expect(km).toBeLessThan(5580)
  })

  it("is symmetric", () => {
    const a = { lat: -33.8688, lng: 151.2093 }
    const b = { lat: 35.6762, lng: 139.6503 }
    expect(haversineDistanceMeters(a, b)).toBeCloseTo(haversineDistanceMeters(b, a), 6)
  })
})

describe("effectiveMaxZoom", () => {
  const BASE = 16
  const ABSOLUTE = 20
  const TARGET_PX = 100

  it("uses the base cap for a guess off by hundreds of kilometers - no boost needed", () => {
    const pin = { lat: 48.8566, lng: 2.3522 } // Paris
    const actual = { lat: 52.52, lng: 13.405 } // Berlin
    expect(effectiveMaxZoom(pin, actual, BASE, ABSOLUTE, TARGET_PX)).toBe(BASE)
  })

  it("pushes above the base cap for a close guess (tens of meters off)", () => {
    const pin = { lat: 48.8566, lng: 2.3522 }
    const actual = { lat: 48.85665, lng: 2.35225 } // a handful of meters away
    const zoom = effectiveMaxZoom(pin, actual, BASE, ABSOLUTE, TARGET_PX)
    expect(zoom).toBeGreaterThan(BASE)
    expect(zoom).toBeLessThanOrEqual(ABSOLUTE)
  })

  it("caps at the absolute ceiling for a near-identical guess", () => {
    const pin = { lat: 48.8566, lng: 2.3522 }
    const actual = { lat: 48.8566, lng: 2.3522 } // distance < 1m -> the early-return branch
    expect(effectiveMaxZoom(pin, actual, BASE, ABSOLUTE, TARGET_PX)).toBe(ABSOLUTE)
  })

  it("never drops below the base cap even for a moderately-far guess", () => {
    const pin = { lat: 0, lng: 0 }
    const actual = { lat: 0, lng: 1 } // ~111km at the equator
    expect(effectiveMaxZoom(pin, actual, BASE, ABSOLUTE, TARGET_PX)).toBe(BASE)
  })
})

describe("antimeridianSafeLngLats", () => {
  it("leaves an ordinary pair (same side of the antimeridian) untouched", () => {
    const pin = { lat: 48.8566, lng: 2.3522 }
    const actual = { lat: 52.52, lng: 13.405 }
    expect(antimeridianSafeLngLats(pin, actual)).toEqual([pin, actual])
  })

  it("unwraps the short way for a guess in Japan vs. the real spot in the US", () => {
    const pin = { lat: 35.6762, lng: 139.6503 } // Tokyo
    const actual = { lat: 29.7604, lng: -95.3698 } // Houston
    const [safePin, safeActual] = antimeridianSafeLngLats(pin, actual)

    expect(safePin).toEqual(pin)
    // Unwrapped past 180 rather than left at -95.3698 - the raw diff (139.65 - (-95.37) = 235) was
    // > 180, so the short way is reached by pushing actual's longitude up past 180 instead.
    expect(safeActual.lng).toBeGreaterThan(180)
    expect(Math.abs(safePin.lng - safeActual.lng)).toBeLessThanOrEqual(180)
  })

  it("unwraps the other direction when actual is the one east of the antimeridian", () => {
    const pin = { lat: 29.7604, lng: -95.3698 } // Houston
    const actual = { lat: 35.6762, lng: 139.6503 } // Tokyo
    const [safePin, safeActual] = antimeridianSafeLngLats(pin, actual)

    expect(safePin).toEqual(pin)
    expect(safeActual.lng).toBeLessThan(-180)
    expect(Math.abs(safePin.lng - safeActual.lng)).toBeLessThanOrEqual(180)
  })
})
