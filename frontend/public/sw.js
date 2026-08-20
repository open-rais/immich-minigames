// The bare minimum Chrome requires before it will offer "Install app" - activate immediately and
// handle `fetch` (even as a pure passthrough). No caching logic yet.
self.addEventListener("install", () => {
  self.skipWaiting()
})

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request))
})
