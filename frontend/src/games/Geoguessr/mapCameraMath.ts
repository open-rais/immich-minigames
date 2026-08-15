// Pure camera-fitting math for MapPicker.tsx's post-reveal fitBounds call - no MapLibre types here
// (testable without mocking a map instance), same "extract the pure math into a sibling *Math.ts"
// convention as Dateguessr's rulerMath.ts.

export interface LatLng {
  lat: number
  lng: number
}

const EARTH_RADIUS_M = 6_371_000
// Meters/pixel at zoom 0, latitude 0, for the standard 256px slippy-map tile - the constant every
// Web Mercator zoom<->meters conversion is built from.
const WEB_MERCATOR_ZOOM0_MPP = 156543.03392

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180
}

// Great-circle distance between two points, in meters.
export function haversineDistanceMeters(a: LatLng, b: LatLng): number {
  const dLat = toRadians(b.lat - a.lat)
  const dLng = toRadians(b.lng - a.lng)
  const lat1 = toRadians(a.lat)
  const lat2 = toRadians(b.lat)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)))
}

// The zoom level at which `distanceMeters` renders as exactly `targetPx` on screen, at the given
// latitude - solved from the standard Web Mercator meters-per-pixel formula
// (WEB_MERCATOR_ZOOM0_MPP * cos(lat) / 2^zoom = distanceMeters / targetPx).
function zoomForPixelSeparation(distanceMeters: number, latitude: number, targetPx: number): number {
  const requiredMetersPerPixel = distanceMeters / targetPx
  return Math.log2((WEB_MERCATOR_ZOOM0_MPP * Math.cos(toRadians(latitude))) / requiredMetersPerPixel)
}

// The maxZoom to hand fitBounds. fitBounds always picks min(the bbox's own natural zoom, this
// cap) - for a near-zero bbox (a guess that landed close to the real spot) the natural zoom
// diverges, so the cap itself becomes the zoom that actually gets used. That's why this can't just
// be one fixed constant: `baseMaxZoom` alone is plenty (and shouldn't be exceeded) for a guess
// that's off by kilometers, but a guess off by only a few dozen meters needs to be pushed much
// closer - up to `absoluteMaxZoom` - or the two pins render on top of each other regardless of how
// generous the flat cap is. For a genuinely ~0 distance there's no zoom level that helps -
// `absoluteMaxZoom` is the best this can offer there, not a guarantee of visible separation.
export function effectiveMaxZoom(
  pin: LatLng,
  actual: LatLng,
  baseMaxZoom: number,
  absoluteMaxZoom: number,
  targetPx: number,
): number {
  const distanceMeters = haversineDistanceMeters(pin, actual)
  if (distanceMeters < 1) return absoluteMaxZoom
  const midLat = (pin.lat + actual.lat) / 2
  const separationZoom = zoomForPixelSeparation(distanceMeters, midLat, targetPx)
  return Math.min(Math.max(separationZoom, baseMaxZoom), absoluteMaxZoom)
}

// LngLatBounds built via .extend() on raw longitudes takes the long way around when the two points
// straddle the antimeridian (a guess in Japan, the real spot in the US) - unwrapping whichever side
// is farther by ±360° first makes the short way win instead. fitBounds/LngLatBounds handle a bound
// outside ±180° fine (a documented antimeridian workaround), so this doesn't need to re-normalize
// the result back into range.
export function antimeridianSafeLngLats(pin: LatLng, actual: LatLng): [LatLng, LatLng] {
  const delta = actual.lng - pin.lng
  if (delta > 180) return [pin, { ...actual, lng: actual.lng - 360 }]
  if (delta < -180) return [pin, { ...actual, lng: actual.lng + 360 }]
  return [pin, actual]
}
