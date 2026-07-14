import type { ExpressionSpecification, StyleSpecification } from "maplibre-gl"

import type { ResolvedTheme } from "../../theme/themeContext"

/**
 * A static, curated recolor of OpenFreeMap's "Positron" style (fetched once from
 * https://tiles.openfreemap.org/styles/positron and trimmed down here), not a runtime
 * fetch-and-patch - see games/Geoguessr/mapStyle.ts's usage in MapPicker.tsx and
 * docs/ARCHITECTURE/FRONTEND.md-adjacent reasoning: the convenience style-JSON endpoint is a
 * softer contract than the tile-data endpoint it still points at (`sources.openmaptiles.url`),
 * so baking it here means an upstream layer-id rename can't silently break or throw at
 * game-start in production - only the tile *data* endpoint needs to keep working.
 *
 * Colors are the hex equivalents of index.css's `--color-*` tokens, light and dark (MapLibre's
 * style JSON needs literal color strings, not CSS `var()`) - kept in sync by hand, same
 * manual-sync convention already used for api/types.ts vs backend/src/api/schemas.py. Roads/rail/
 * aeroway layers and the sprite-based place-dot icons are dropped entirely (irrelevant clutter at
 * the world-guess zoom levels this map is used at) - only land/water/boundaries/place labels
 * remain.
 */

const LIGHT = {
  MAP_BG: "#f3f5f9", // --color-map-bg
  MAP_WATER: "#ced8ec", // --color-map-water
  MAP_LAND: "#e4e8f0", // --color-map-land
  MAP_LAND_DARK: "#d6dbe4", // building outline, one step darker than --color-map-land
  LINE_STRONG: "#d3d8e0", // --color-line-strong
  INK: "#11161f", // --color-ink
  BODY: "#2d333d", // --color-body
  MUTED: "#5d646f", // --color-muted
  PRIMARY: "#3055b6", // --color-primary
}

const DARK = {
  MAP_BG: "#0c0d11", // --color-map-bg (.dark)
  MAP_WATER: "#222f3f", // --color-map-water (.dark)
  MAP_LAND: "#1c1f26", // --color-map-land (.dark)
  MAP_LAND_DARK: "#292e36", // building outline, one step lighter than --color-map-land (.dark)
  LINE_STRONG: "#393d44", // --color-line-strong (.dark)
  INK: "#e3e8f0", // --color-ink (.dark)
  BODY: "#c9ced6", // --color-body (.dark)
  MUTED: "#9399a2", // --color-muted (.dark)
  PRIMARY: "#a5c9ff", // --color-primary (.dark)
}

// Explicitly typed (not `as const`) - MapLibre's expression types need a mutable array, and
// `as const` would freeze this into a readonly tuple that then can't be spread into each layer's
// layout object below.
const placeNameField: ExpressionSpecification = [
  "case",
  ["has", "name:nonlatin"],
  ["concat", ["get", "name:latin"], "\n", ["get", "name:nonlatin"]],
  ["coalesce", ["get", "name_en"], ["get", "name"]],
]
const placeLabelLayout: { "text-field": ExpressionSpecification; "text-max-width": number } = {
  "text-field": placeNameField,
  "text-max-width": 8,
}

export function buildGeoguessrMapStyle(resolved: ResolvedTheme): StyleSpecification {
  const { MAP_BG, MAP_WATER, MAP_LAND, MAP_LAND_DARK, LINE_STRONG, INK, BODY, MUTED, PRIMARY } =
    resolved === "dark" ? DARK : LIGHT

  return {
    version: 8,
    glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
    sources: {
      openmaptiles: {
        type: "vector",
        url: "https://tiles.openfreemap.org/planet",
      },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": MAP_BG } },
      {
        id: "park",
        type: "fill",
        source: "openmaptiles",
        "source-layer": "park",
        paint: { "fill-color": MAP_LAND },
      },
      {
        id: "water",
        type: "fill",
        source: "openmaptiles",
        "source-layer": "water",
        paint: { "fill-antialias": true, "fill-color": MAP_WATER },
      },
      {
        id: "landcover_wood",
        type: "fill",
        source: "openmaptiles",
        "source-layer": "landcover",
        minzoom: 10,
        paint: {
          "fill-color": MAP_LAND,
          "fill-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0, 12, 1],
        },
      },
      {
        id: "landuse_residential",
        type: "fill",
        source: "openmaptiles",
        "source-layer": "landuse",
        maxzoom: 16,
        paint: {
          "fill-color": MAP_LAND,
          "fill-opacity": ["interpolate", ["exponential", 0.6], ["zoom"], 8, 0.8, 9, 0.6],
        },
      },
      {
        id: "building",
        type: "fill",
        source: "openmaptiles",
        "source-layer": "building",
        minzoom: 12,
        paint: { "fill-antialias": true, "fill-color": MAP_LAND, "fill-outline-color": MAP_LAND_DARK },
      },
      {
        id: "boundary_2",
        type: "line",
        source: "openmaptiles",
        "source-layer": "boundary",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": LINE_STRONG,
          "line-opacity": ["interpolate", ["linear"], ["zoom"], 0, 0.4, 4, 1],
          "line-width": ["interpolate", ["linear"], ["zoom"], 3, 1, 5, 1.2, 12, 3],
        },
      },
      {
        id: "boundary_3",
        type: "line",
        source: "openmaptiles",
        "source-layer": "boundary",
        minzoom: 8,
        paint: {
          "line-color": LINE_STRONG,
          "line-dasharray": [1, 1],
          "line-width": ["interpolate", ["linear"], ["zoom"], 7, 1, 11, 2],
        },
      },
      {
        id: "boundary_disputed",
        type: "line",
        source: "openmaptiles",
        "source-layer": "boundary",
        paint: {
          "line-color": LINE_STRONG,
          "line-dasharray": [1, 2],
          "line-width": ["interpolate", ["linear"], ["zoom"], 3, 1, 5, 1.2, 12, 3],
        },
      },
      {
        id: "water_name_point_label",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "water_name",
        layout: {
          ...placeLabelLayout,
          "text-font": ["Noto Sans Italic"],
          "text-letter-spacing": 0.2,
          "text-size": ["interpolate", ["linear"], ["zoom"], 0, 10, 8, 14],
        },
        paint: { "text-color": PRIMARY, "text-halo-color": MAP_BG, "text-halo-width": 1.5 },
      },
      {
        id: "label_country_1",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "place",
        maxzoom: 9,
        layout: {
          ...placeLabelLayout,
          "text-font": ["Noto Sans Bold"],
          "text-size": ["interpolate", ["linear"], ["zoom"], 1, 9, 4, 17],
        },
        paint: { "text-color": INK, "text-halo-blur": 1, "text-halo-color": MAP_BG, "text-halo-width": 1 },
      },
      {
        id: "label_country_2",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "place",
        maxzoom: 9,
        layout: {
          ...placeLabelLayout,
          "text-font": ["Noto Sans Bold"],
          "text-size": ["interpolate", ["linear"], ["zoom"], 2, 9, 5, 17],
        },
        paint: { "text-color": INK, "text-halo-blur": 1, "text-halo-color": MAP_BG, "text-halo-width": 1 },
      },
      {
        id: "label_country_3",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "place",
        minzoom: 2,
        maxzoom: 9,
        layout: {
          ...placeLabelLayout,
          "text-font": ["Noto Sans Bold"],
          "text-size": ["interpolate", ["linear"], ["zoom"], 3, 9, 7, 17],
        },
        paint: { "text-color": INK, "text-halo-blur": 1, "text-halo-color": MAP_BG, "text-halo-width": 1 },
      },
      {
        id: "label_state",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "place",
        minzoom: 5,
        maxzoom: 8,
        layout: {
          ...placeLabelLayout,
          "text-font": ["Noto Sans Italic"],
          "text-letter-spacing": 0.2,
          "text-size": ["interpolate", ["linear"], ["zoom"], 5, 10, 8, 14],
          "text-transform": "uppercase",
        },
        paint: { "text-color": MUTED, "text-halo-blur": 1, "text-halo-color": MAP_BG, "text-halo-width": 1 },
      },
      {
        id: "label_city",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "place",
        minzoom: 3,
        layout: {
          ...placeLabelLayout,
          "text-anchor": "center",
          "text-font": ["Noto Sans Regular"],
          "text-size": ["interpolate", ["exponential", 1.2], ["zoom"], 4, 11, 7, 13, 11, 18],
        },
        paint: { "text-color": INK, "text-halo-blur": 1, "text-halo-color": MAP_BG, "text-halo-width": 1 },
      },
      {
        id: "label_city_capital",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "place",
        minzoom: 3,
        layout: {
          ...placeLabelLayout,
          "text-anchor": "center",
          "text-font": ["Noto Sans Bold"],
          "text-size": ["interpolate", ["exponential", 1.2], ["zoom"], 4, 12, 7, 14, 11, 20],
        },
        paint: { "text-color": INK, "text-halo-blur": 1, "text-halo-color": MAP_BG, "text-halo-width": 1 },
      },
      {
        id: "label_town",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "place",
        minzoom: 6,
        layout: {
          ...placeLabelLayout,
          "text-anchor": "center",
          "text-font": ["Noto Sans Regular"],
          "text-size": ["interpolate", ["exponential", 1.2], ["zoom"], 7, 12, 11, 14],
        },
        paint: { "text-color": BODY, "text-halo-blur": 1, "text-halo-color": MAP_BG, "text-halo-width": 1 },
      },
      {
        id: "label_other",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "place",
        minzoom: 8,
        layout: {
          ...placeLabelLayout,
          "text-font": ["Noto Sans Italic"],
          "text-letter-spacing": 0.1,
          "text-size": ["interpolate", ["linear"], ["zoom"], 8, 9, 12, 10],
          "text-transform": "uppercase",
        },
        paint: { "text-color": MUTED, "text-halo-blur": 1, "text-halo-color": MAP_BG, "text-halo-width": 1 },
      },
    ],
  }
}
