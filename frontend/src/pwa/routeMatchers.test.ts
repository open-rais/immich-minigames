import { describe, expect, it } from "vitest"
import { isConfigPath, isStaticAssetPath, isThumbnailPath } from "./routeMatchers"

describe("isStaticAssetPath", () => {
  it("matches the logo, apple touch icon, and any icon-* file", () => {
    expect(isStaticAssetPath("/logo.svg")).toBe(true)
    expect(isStaticAssetPath("/apple-touch-icon.png")).toBe(true)
    expect(isStaticAssetPath("/icon-512.png")).toBe(true)
    expect(isStaticAssetPath("/icon-maskable-512.png")).toBe(true)
  })

  it("matches any path under /covers/", () => {
    expect(isStaticAssetPath("/covers/geoguessr.webp")).toBe(true)
  })

  it("rejects hashed assets and API paths", () => {
    expect(isStaticAssetPath("/assets/index-abc123.js")).toBe(false)
    expect(isStaticAssetPath("/api/v1/config")).toBe(false)
  })
})

describe("isThumbnailPath", () => {
  it("matches person, asset, and album thumbnail routes", () => {
    expect(isThumbnailPath("/api/v1/people/abc-123/thumbnail")).toBe(true)
    expect(isThumbnailPath("/api/v1/assets/abc-123/thumbnail")).toBe(true)
    expect(isThumbnailPath("/api/v1/albums/abc-123/thumbnail")).toBe(true)
  })

  it("rejects an id containing a slash (would cross into a different route)", () => {
    expect(isThumbnailPath("/api/v1/people/abc/123/thumbnail")).toBe(false)
  })

  it("rejects other entity types and non-thumbnail suffixes", () => {
    expect(isThumbnailPath("/api/v1/games/abc-123/thumbnail")).toBe(false)
    expect(isThumbnailPath("/api/v1/people/abc-123")).toBe(false)
  })
})

describe("isConfigPath", () => {
  it("matches exactly /api/v1/config", () => {
    expect(isConfigPath("/api/v1/config")).toBe(true)
  })

  it("rejects a config-prefixed but different path", () => {
    expect(isConfigPath("/api/v1/config/extra")).toBe(false)
    expect(isConfigPath("/api/v1/configuration")).toBe(false)
  })
})
