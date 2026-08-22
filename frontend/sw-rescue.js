// EMERGENCY "rescue" service worker - deliberately NOT wired into the build (not in public/, not
// imported by vite.config.ts) so it can never ship by accident. Plain, dependency-free JS on
// purpose: if a bad src/sw.ts ever gets deployed (a broken runtime-cache route, a shell that
// 404s offline, ...), this is the *only* way to recover an already-installed device - a broken SW
// decides for itself what to fetch, so no server-side fix can reach past it. This one does the
// opposite of everything sw.ts does: tears down every cache and unregisters itself, so the next
// real deploy starts from a clean slate instead of layering a fix on top of whatever's still
// cached.
//
// HOW TO USE:
//   1. npm run build                    - produces dist/ as normal
//   2. cp sw-rescue.js dist/sw.js       - overwrite the just-built one with this file
//   3. Deploy that dist/ as usual. nginx.conf.template serves /sw.js with
//      Cache-Control: no-cache, so this reaches each device on its next SW update check (see
//      register.ts's UPDATE_CHECK_INTERVAL_MS) - not instant, and browsers cap how often they'll
//      even ask (up to 24h), so give this at least a day or two before assuming a device is fixed.
//   4. Once you're confident every active device has picked it up, revert: rebuild and redeploy
//      normally (npm run build, no override) so devices get the real sw.ts back and PWA features
//      (offline shell, push) resume.

self.addEventListener("install", () => self.skipWaiting())

self.addEventListener("activate", (event) => {
  event.waitUntil(
    Promise.all([
      self.registration.unregister(),
      caches.keys().then((keys) => Promise.all(keys.map((key) => caches.delete(key)))),
    ])
      .then(() => self.clients.matchAll({ type: "window" }))
      .then((clients) => clients.forEach((client) => client.navigate(client.url))),
  )
})
