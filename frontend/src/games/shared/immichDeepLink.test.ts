// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"

import { androidIntentUrl, detectMobilePlatform, openInImmichApp } from "./immichDeepLink"

// jsdom's navigator has no maxTouchPoints, so these are defined outright rather than spied on.
const original = {
  userAgent: navigator.userAgent,
  maxTouchPoints: navigator.maxTouchPoints,
}

function stubUserAgent(userAgent: string, maxTouchPoints = 0) {
  Object.defineProperty(navigator, "userAgent", { configurable: true, value: userAgent })
  Object.defineProperty(navigator, "maxTouchPoints", { configurable: true, value: maxTouchPoints })
}

afterEach(() => {
  Object.defineProperty(navigator, "userAgent", { configurable: true, value: original.userAgent })
  Object.defineProperty(navigator, "maxTouchPoints", {
    configurable: true,
    value: original.maxTouchPoints,
  })
})

describe("detectMobilePlatform", () => {
  it("detects Android", () => {
    stubUserAgent("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/126")
    expect(detectMobilePlatform()).toBe("android")
  })

  it("detects iOS", () => {
    stubUserAgent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15")
    expect(detectMobilePlatform()).toBe("ios")
  })

  it("detects an iPad reporting itself as a Mac by its touch points", () => {
    stubUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15", 5)
    expect(detectMobilePlatform()).toBe("ios")
  })

  it("returns null on a real desktop Mac", () => {
    stubUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126")
    expect(detectMobilePlatform()).toBeNull()
  })

  it("returns null on desktop Windows", () => {
    stubUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126")
    expect(detectMobilePlatform()).toBeNull()
  })
})

describe("androidIntentUrl", () => {
  it("keeps the deep link's host and query while carrying the web URL as the fallback", () => {
    const url = androidIntentUrl("immich://asset?id=abc-123", "https://photos.example.com/photos/abc-123")
    expect(url).toBe(
      "intent://asset?id=abc-123#Intent;scheme=immich;package=app.alextran.immich;" +
        "S.browser_fallback_url=https%3A%2F%2Fphotos.example.com%2Fphotos%2Fabc-123;end",
    )
  })
})

describe("openInImmichApp", () => {
  const appUrl = "immich://people?id=p1"
  const webUrl = "https://photos.example.com/people/p1"

  function fakeTab() {
    return { closed: false, location: { href: "about:blank" } } as unknown as Window
  }

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it("opens the deep link in a new tab, leaving the current one alone", () => {
    stubUserAgent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15")
    const open = vi.spyOn(window, "open").mockReturnValue(fakeTab())

    openInImmichApp("ios", appUrl, webUrl)

    expect(open).toHaveBeenCalledWith(appUrl, "_blank")
  })

  it("opens Android's intent URL rather than the bare scheme", () => {
    const open = vi.spyOn(window, "open").mockReturnValue(fakeTab())

    openInImmichApp("android", appUrl, webUrl)

    expect(open).toHaveBeenCalledWith(androidIntentUrl(appUrl, webUrl), "_blank")
  })

  it("sends the new tab to Immich's web UI when nothing handled the deep link", () => {
    vi.useFakeTimers()
    const tab = fakeTab()
    vi.spyOn(window, "open").mockReturnValue(tab)

    openInImmichApp("ios", appUrl, webUrl)
    vi.runAllTimers()

    expect(tab.location.href).toBe(webUrl)
  })

  it("leaves a tab the app or the browser already took somewhere else alone", () => {
    vi.useFakeTimers()
    const tab = fakeTab()
    vi.spyOn(window, "open").mockReturnValue(tab)

    openInImmichApp("android", appUrl, webUrl)
    tab.location.href = "https://photos.example.com/people/someone-else"
    vi.runAllTimers()

    expect(tab.location.href).toBe("https://photos.example.com/people/someone-else")
  })
})
