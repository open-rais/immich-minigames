import type { Feature, LineString } from "geojson"
import { useEffect, useRef, useState } from "react"
import type { MapMouseEvent } from "maplibre-gl"
import { GeoJSONSource, LngLatBounds, MapLibreMap, Marker } from "maplibre-gl"
import "maplibre-gl/dist/maplibre-gl.css"

import { useTheme } from "../../theme/useTheme"
import { buildGeoguessrMapStyle } from "./mapStyle"

// Matches Tailwind's `md:` breakpoint - same convention MoreOrLessGame.tsx uses to distinguish
// desktop/mobile behavior at interaction time rather than via separate components.
const MOBILE_BREAKPOINT_QUERY = "(min-width: 768px)"

// MapLibre's Marker needs a literal color string (no CSS var()), so the guess marker tracks
// --color-primary's light/dark values by hand - see mapStyle.ts's LIGHT/DARK palettes.
const GUESS_MARKER_COLOR = { light: "#3055b6", dark: "#a5c9ff" }
// tailwind rose-600, matches CandidateCard's existing "incorrect/highlight" accent - kept
// identical in both themes (already proven legible on a dark surface there), no dark variant.
const ACTUAL_MARKER_COLOR = "#e11d48"
const REVEAL_LINE_SOURCE_ID = "geoguessr-reveal-line"

type LatLng = { lat: number; lng: number }

interface MapPickerProps {
  pin: LatLng | null
  onPinChange: (pin: LatLng) => void
  actual?: LatLng | null
  disabled?: boolean
  forceExpanded?: boolean
}

function isDesktop(): boolean {
  return window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches
}

function setRevealLine(map: MapLibreMap, guess: LatLng, actual: LatLng) {
  const geojson: Feature<LineString> = {
    type: "Feature",
    properties: {},
    geometry: {
      type: "LineString",
      coordinates: [
        [guess.lng, guess.lat],
        [actual.lng, actual.lat],
      ],
    },
  }
  const source = map.getSource(REVEAL_LINE_SOURCE_ID) as GeoJSONSource | undefined
  if (source) {
    source.setData(geojson)
    return
  }
  map.addSource(REVEAL_LINE_SOURCE_ID, { type: "geojson", data: geojson })
  map.addLayer({
    id: REVEAL_LINE_SOURCE_ID,
    type: "line",
    source: REVEAL_LINE_SOURCE_ID,
    paint: { "line-color": ACTUAL_MARKER_COLOR, "line-width": 2, "line-dasharray": [2, 2] },
  })
}

function removeRevealLine(map: MapLibreMap) {
  if (map.getLayer(REVEAL_LINE_SOURCE_ID)) map.removeLayer(REVEAL_LINE_SOURCE_ID)
  if (map.getSource(REVEAL_LINE_SOURCE_ID)) map.removeSource(REVEAL_LINE_SOURCE_ID)
}

export function MapPicker({ pin, onPinChange, actual = null, disabled = false, forceExpanded = false }: MapPickerProps) {
  const { resolved } = useTheme()
  const containerRef = useRef<HTMLDivElement>(null)
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const guessMarkerRef = useRef<Marker | null>(null)
  const actualMarkerRef = useRef<Marker | null>(null)

  const [internalExpanded, setInternalExpanded] = useState(false)
  const expanded = forceExpanded || internalExpanded

  // Refs so the map's click listener (attached once, see below) always sees the latest values
  // without needing to be torn down/reattached on every prop/state change.
  const onPinChangeRef = useRef(onPinChange)
  onPinChangeRef.current = onPinChange
  const disabledRef = useRef(disabled)
  disabledRef.current = disabled
  const expandedRef = useRef(expanded)
  expandedRef.current = expanded

  useEffect(() => {
    if (!mapContainerRef.current) return

    const map = new MapLibreMap({
      container: mapContainerRef.current,
      style: buildGeoguessrMapStyle(resolved),
      center: [0, 20],
      zoom: 1.2,
      // Hidden per product decision - the OpenStreetMap attribution link made it hard to tap the
      // small collapsed map to expand it on mobile. The underlying data is still OSM (ODbL), see
      // mapStyle.ts - if this ever needs revisiting, a compact `{ compact: true }` control was
      // here before.
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
    })
    mapRef.current = map

    function handleClick(e: MapMouseEvent) {
      // Ignore clicks while collapsed (mobile's first tap only expands, doesn't place a pin -
      // too imprecise at that size anyway) or while a guess isn't editable (post-submit reveal).
      if (!expandedRef.current || disabledRef.current) return
      onPinChangeRef.current({ lat: e.lngLat.lat, lng: e.lngLat.lng })
    }
    map.on("click", handleClick)

    return () => {
      map.remove()
      mapRef.current = null
      // Markers belong to the removed map's DOM, not just its style - drop the refs too so the
      // effects below recreate them (with the right theme's color) against the next map instead
      // of reusing a stale, already-colored instance.
      guessMarkerRef.current = null
      actualMarkerRef.current = null
    }
    // `resolved` triggers a full remount on theme change (camera/zoom reset is accepted) since
    // MapLibre's style JSON needs literal colors, not CSS var() - see mapStyle.ts.
  }, [resolved])

  // The collapsed corner map shouldn't trap page scroll/pinch - only interactive once expanded.
  // Also re-applied on `resolved` - a freshly remounted map defaults to MapLibre's normal
  // interactivity regardless of the current collapsed/expanded state.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (expanded) {
      map.dragPan.enable()
      map.scrollZoom.enable()
      map.touchZoomRotate.enable()
      map.doubleClickZoom.enable()
    } else {
      map.dragPan.disable()
      map.scrollZoom.disable()
      map.touchZoomRotate.disable()
      map.doubleClickZoom.disable()
    }
  }, [expanded, resolved])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (!pin) {
      guessMarkerRef.current?.remove()
      guessMarkerRef.current = null
      return
    }
    if (!guessMarkerRef.current) {
      guessMarkerRef.current = new Marker({ color: GUESS_MARKER_COLOR[resolved] })
    }
    guessMarkerRef.current.setLngLat([pin.lng, pin.lat]).addTo(map)
  }, [pin, resolved])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    function apply() {
      if (!actual) {
        actualMarkerRef.current?.remove()
        actualMarkerRef.current = null
        removeRevealLine(map!)
        return
      }
      if (!actualMarkerRef.current) {
        actualMarkerRef.current = new Marker({ color: ACTUAL_MARKER_COLOR })
      }
      actualMarkerRef.current.setLngLat([actual.lng, actual.lat]).addTo(map!)

      if (pin) {
        setRevealLine(map!, pin, actual)
        // LngLatBounds's constructor expects its two args pre-sorted (sw, ne) - building it via
        // .extend() from two arbitrary points instead avoids passing them in the wrong order,
        // which produces an inverted/invalid box and makes fitBounds jump to a bogus view.
        const bounds = new LngLatBounds()
        bounds.extend([pin.lng, pin.lat])
        bounds.extend([actual.lng, actual.lat])
        map!.fitBounds(bounds, { padding: 48, maxZoom: 6, duration: 600 })
      }
    }

    if (map.isStyleLoaded()) apply()
    else map.once("load", apply)
  }, [actual, pin, resolved])

  function handleMouseEnter() {
    if (isDesktop()) setInternalExpanded(true)
  }

  function handleMouseLeave() {
    if (isDesktop()) setInternalExpanded(false)
  }

  function handleContainerClick() {
    if (isDesktop()) return
    if (!internalExpanded) setInternalExpanded(true)
    // Already expanded: a tap here is a tap on the map itself (placing a pin), handled by the
    // map's own click listener above - this handler has nothing extra to do.
  }

  function handleTransitionEnd(e: React.TransitionEvent<HTMLDivElement>) {
    if (e.target !== e.currentTarget) return
    if (e.propertyName !== "width" && e.propertyName !== "height") return
    mapRef.current?.resize()
  }

  // Tap-outside-to-collapse on mobile - a document-level listener active only while expanded (and
  // not forced open), since the photo behind the map has no dedicated "collapse" handler of its
  // own; tapping it is just "a click outside the map's container".
  useEffect(() => {
    if (!internalExpanded || forceExpanded) return
    function handleDocumentClick(e: MouseEvent) {
      if (isDesktop()) return
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setInternalExpanded(false)
      }
    }
    document.addEventListener("click", handleDocumentClick)
    return () => document.removeEventListener("click", handleDocumentClick)
  }, [internalExpanded, forceExpanded])

  return (
    <div
      ref={containerRef}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleContainerClick}
      onTransitionEnd={handleTransitionEnd}
      className={`fixed bottom-[18px] right-[18px] z-20 overflow-hidden rounded-2xl border border-line bg-map-bg shadow-card transition-[width,height] duration-300 ease-out md:right-10 md:bottom-7 ${
        expanded ? "h-[70vh] w-[92vw] md:h-[65vh] md:w-[520px]" : "h-32 w-32 md:h-40 md:w-40"
      }`}
    >
      <div ref={mapContainerRef} className="h-full w-full" />
    </div>
  )
}
