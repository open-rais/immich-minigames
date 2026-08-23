// Opening an entity in Immich from a phone should land in the Immich *app* when it's installed and
// in the browser otherwise, which no single URL can express: `immich://` opens the app but dead-ends
// without it, and the web URL never opens the app. So the platform decides how the click is
// handled, and each mobile platform gets the fallback mechanism its browsers actually support.

const ANDROID_PACKAGE = "app.alextran.immich"

export type MobilePlatform = "android" | "ios" | null

// Long enough for the app to take the new tab over, short enough that a phone without the app
// doesn't sit on a blank tab. Android waits longer because it's the platform that puts an "¿Abrir en
// Immich?" confirmation between the click and the app switch, and while that dialog is up the tab
// looks exactly like one nothing happened in.
const FALLBACK_DELAY_MS: Record<NonNullable<MobilePlatform>, number> = {
  android: 2500,
  ios: 1200,
}

/** null on anything that can't have the Immich app installed - desktop, where the plain web link is
 * the whole story. */
export function detectMobilePlatform(): MobilePlatform {
  const ua = navigator.userAgent
  if (/Android/i.test(ua)) return "android"
  if (/iPhone|iPad|iPod/i.test(ua)) return "ios"
  // iPadOS 13+ claims to be a Mac, so touch points are the only thing separating it from a desktop.
  if (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1) return "ios"
  return null
}

/** `immich://asset?id=x` -> the equivalent `intent://` URL, which Android browsers resolve
 * themselves: the app if it's installed, browser_fallback_url if it isn't. */
export function androidIntentUrl(appUrl: string, webUrl: string): string {
  const target = appUrl.replace(/^immich:\/\//, "")
  const fallback = encodeURIComponent(webUrl)
  return `intent://${target}#Intent;scheme=immich;package=${ANDROID_PACKAGE};S.browser_fallback_url=${fallback};end`
}

// The whole attempt happens in a tab of its own, so the game's tab is never navigated away from -
// neither by the deep link, nor by the browser's own fallback, nor by ours. It has to be opened
// synchronously from the click handler (that's what makes it user-initiated rather than a blocked
// popup), which also means it, not this page, is the one that ends up foregrounded.
function openDeepLinkTab(deepLink: string): Window | null {
  return window.open(deepLink, "_blank")
}

// Last-resort fallback for whatever the browser didn't handle on its own: iOS' custom scheme has no
// fallback URL to fail into, and an in-app webview may just ignore `intent://`. A tab that's still
// sitting on about:blank is the tell that nothing happened - anything that did handle the link took
// the tab somewhere (Immich's web UI, an error page), leaving it either off about:blank or
// cross-origin and unreadable.
function scheduleTabFallback(tab: Window, webUrl: string, delayMs: number): void {
  window.setTimeout(() => {
    try {
      if (tab.closed || tab.location.href !== "about:blank") return
    } catch {
      return // navigated cross-origin, i.e. handled
    }
    tab.location.href = webUrl
  }, delayMs)
}

// Fallback for the fallback: with no tab to work with, the current one is all that's left. Cancelled
// as soon as the page is hidden, which is what "the app took over" looks like from here.
function scheduleSameTabFallback(webUrl: string, delayMs: number): void {
  let timer = 0
  let done = false

  const cancel = () => {
    if (done) return
    done = true
    window.clearTimeout(timer)
    document.removeEventListener("visibilitychange", onVisibilityChange)
    window.removeEventListener("pagehide", cancel)
  }
  const onVisibilityChange = () => {
    if (document.hidden) cancel()
  }

  timer = window.setTimeout(() => {
    if (done || document.hidden) return
    cancel()
    window.location.href = webUrl
  }, delayMs)

  document.addEventListener("visibilitychange", onVisibilityChange)
  window.addEventListener("pagehide", cancel)
}

/** Opens the Immich app on a phone, falling back to Immich's web UI when it isn't installed - both
 * in a new tab, leaving the game's own tab untouched. Only call this on a mobile platform (see
 * detectMobilePlatform) - elsewhere the web URL is the answer. */
export function openInImmichApp(
  platform: NonNullable<MobilePlatform>,
  appUrl: string,
  webUrl: string,
): void {
  // A bare `immich://` navigation on Android gives an ERR_UNKNOWN_URL_SCHEME error page when the app
  // is missing; `intent://` fails soft into browser_fallback_url instead - inside the new tab, since
  // that's the one the browser is navigating.
  const deepLink = platform === "android" ? androidIntentUrl(appUrl, webUrl) : appUrl
  const delayMs = FALLBACK_DELAY_MS[platform]

  const tab = openDeepLinkTab(deepLink)
  if (tab) {
    scheduleTabFallback(tab, webUrl, delayMs)
    return
  }

  // Popups blocked (some in-app webviews, a hardened browser setting): losing the deep link
  // entirely would be worse than reusing this tab, which is what the link did before any of this.
  window.location.href = deepLink
  scheduleSameTabFallback(webUrl, delayMs)
}
