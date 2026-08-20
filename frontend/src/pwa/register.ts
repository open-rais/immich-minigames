// Registration is gated on the feature-detect itself: `serviceWorker` in `navigator` is only
// true in a secure context (https:// or localhost), so this silently no-ops everywhere else
// instead of throwing.
export function registerServiceWorker(): void {
  if (!("serviceWorker" in navigator)) return

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error: unknown) => {
      console.error("Service worker registration failed", error)
    })
  })
}
