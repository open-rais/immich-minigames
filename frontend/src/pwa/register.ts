// Registration is gated on the feature-detect itself: `serviceWorker` in `navigator` is only
// true in a secure context (https:// or localhost), so this silently no-ops everywhere else
// instead of throwing.
const UPDATE_CHECK_INTERVAL_MS = 60 * 60 * 1000

export function registerServiceWorker(): void {
  if (!("serviceWorker" in navigator)) return

  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then((registration) => {
        let lastUpdateCheck = Date.now()
        document.addEventListener("visibilitychange", () => {
          if (document.visibilityState !== "visible") return
          const now = Date.now()
          if (now - lastUpdateCheck < UPDATE_CHECK_INTERVAL_MS) return
          lastUpdateCheck = now
          registration.update().catch(() => {})
        })
      })
      .catch((error: unknown) => {
        console.error("Service worker registration failed", error)
      })
  })

  // With skipWaiting()/clientsClaim() in sw.ts, a new worker can take control mid-session while
  // the open tab still references chunk URLs from the precache it just replaced - the next
  // dynamic import() of another game would 404. Reloading here is what makes skipWaiting safe
  // instead of a ticking "Failed to fetch dynamically imported module".
  let reloading = false
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (reloading) return
    reloading = true
    window.location.reload()
  })
}
