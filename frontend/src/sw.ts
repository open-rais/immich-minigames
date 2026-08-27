/// <reference lib="webworker" />
export type {}
declare const self: ServiceWorkerGlobalScope

import { clientsClaim } from "workbox-core"
import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching"
import { registerRoute } from "workbox-routing"
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from "workbox-strategies"
import { ExpirationPlugin } from "workbox-expiration"
import type { WorkboxPlugin } from "workbox-core"
import { urlBase64ToUint8Array } from "./pwa/base64"
import { API_CACHE_NAME } from "./pwa/cacheNames"
import { isConfigPath, isStaticAssetPath, isThumbnailPath } from "./pwa/routeMatchers"

self.skipWaiting()
clientsClaim()

const STATIC_CACHE = "minigames-static-v1"
const SHELL_CACHE = "minigames-shell-v1"

// Shorter than the page's own per-attempt budget (games/shared/imageLoading.ts's IMAGE_TIMEOUT_MS)
// so a request that goes nowhere surfaces as a plain network error the <img> can react to, instead
// of the page having to wait out its own timer for something this worker already knows is dead.
const THUMBNAIL_NETWORK_TIMEOUT_MS = 6_000

// A response the page can safely be handed while a copy of it is also being written to the cache.
//
// Workbox's CacheFirst fetches, calls response.clone(), returns one branch to the page and writes
// the other - and those two branches are a tee over the *network* stream. If they drain at
// different speeds the page's branch can end up stalled even though the cache's branch completed,
// which is exactly the reported bug: a photo stuck on its spinner forever, that appears instantly
// the moment its element is remounted, because by then the bytes are sitting in Cache Storage.
//
// Draining the body here, before Workbox ever sees the response, means the clone it takes
// afterwards is a copy of an in-memory blob rather than a live stream, and neither side can hold
// up the other. It costs the (already small) progressive rendering of a JPEG that this app never
// relied on.
const bufferBeforeCloningPlugin: WorkboxPlugin = {
  fetchDidSucceed: async ({ response }) => {
    // Anything that isn't a plain 200 is passed straight through: a 304 (the page's own
    // If-None-Match, forwarded by this worker) is a null-body status, and constructing a Response
    // with a body for one of those throws.
    if (response.status !== 200) {
      return response
    }
    const blob = await response.blob()
    return new Response(blob, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    })
  },
}

// Workbox exposes networkTimeoutSeconds on NetworkFirst but not on CacheFirst, so the bound goes
// on the request itself.
const networkTimeoutPlugin: WorkboxPlugin = {
  requestWillFetch: async ({ request }) =>
    new Request(request, { signal: AbortSignal.timeout(THUMBNAIL_NETWORK_TIMEOUT_MS) }),
}

cleanupOutdatedCaches()
precacheAndRoute(self.__WB_MANIFEST)

// Every client-routed path serves the identical index.html (nginx's `try_files $uri /index.html`,
// vite dev server's history fallback), so all navigations are pinned to one cache entry instead of
// one per visited path - otherwise a path visited only once online would 404 offline even though
// every other path already has a usable shell cached.
registerRoute(
  ({ request }) => request.mode === "navigate",
  new NetworkFirst({
    cacheName: SHELL_CACHE,
    // Without this, opening the app on a bad connection waits on the network before it will fall
    // back to the shell it already has cached - so the app hangs on a blank screen rather than
    // starting offline-first, which is the entire point of caching the shell.
    networkTimeoutSeconds: 4,
    plugins: [
      {
        cacheKeyWillBeUsed: async () => `${self.location.origin}/index.html`,
      },
    ],
  }),
)

registerRoute(
  ({ url }) => url.origin === self.location.origin && isStaticAssetPath(url.pathname),
  new StaleWhileRevalidate({ cacheName: STATIC_CACHE }),
)

registerRoute(
  ({ url }) => isThumbnailPath(url.pathname),
  new CacheFirst({
    cacheName: API_CACHE_NAME,
    plugins: [
      bufferBeforeCloningPlugin,
      networkTimeoutPlugin,
      // maxAgeSeconds, not StaleWhileRevalidate: the *image* behind a thumbnail id can change
      // (Immich picks a new featured face, an album cover changes, an asset gets rotated/edited),
      // so CacheFirst alone would keep serving a stale one indefinitely until the 300-entry LRU
      // happened to evict it. 14 days bounds that staleness without paying a network request per
      // thumbnail on every load, which is the entire reason this cache exists.
      new ExpirationPlugin({ maxEntries: 300, maxAgeSeconds: 14 * 24 * 60 * 60, purgeOnQuotaError: true }),
    ],
  }),
)

registerRoute(
  ({ url }) => isConfigPath(url.pathname),
  new StaleWhileRevalidate({ cacheName: API_CACHE_NAME }),
)

// Every other /api/v1/* route (daily, games, leaderboard, records, reports, auth, admin) is
// deliberately left unregistered - live per-user data that queryCache.ts already handles with its
// own in-memory stale-while-revalidate, which is where "serve stale while refetching" belongs for
// data that must not survive a logout on disk.

interface PushPayload {
  title: string
  body: string
  url: string
  tag: string
}

// The payload is plain {title, body, url, tag} JSON composed server-side (services/notifications/
// sender.py) - this stays deliberately dumb (no per-notification-type logic) so a future 5th
// notification is backend-only work, never a new SW version every device has to pick up.
self.addEventListener("push", (event) => {
  if (!event.data) return
  let payload: PushPayload
  try {
    payload = event.data.json()
  } catch {
    return
  }
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      tag: payload.tag,
      data: { url: payload.url },
    }),
  )
})

// tag-replaced notifications of the same type instead of stacking; a click focuses an already-open
// tab on that same URL before falling back to opening a new one.
self.addEventListener("notificationclick", (event) => {
  event.notification.close()
  const url = (event.notification.data as { url?: string } | undefined)?.url ?? "/"
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url === url && "focus" in client) return client.focus()
      }
      return self.clients.openWindow(url)
    }),
  )
})

// Fires when the browser rotates a subscription on its own (expiry, or a browser-driven refresh)
// - without this, the new endpoint is never registered anywhere and the device silently stops
// receiving notifications until someone notices and re-activates by hand. The old endpoint needs
// no explicit cleanup here: it's already dead at the push service by the time this fires, so the
// next scheduled send against it 404/410s and sender.py's existing dead-subscription handling
// removes the row, same as any other stale device. Worth the one exception to this file's
// otherwise-dumb-SW convention because it's the one thing that can't be handled from the backend
// or the open app - the browser only ever tells the SW.
self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil(
    fetch("/api/v1/config")
      .then((res) => res.json())
      .then((config: { push_public_key: string | null }) =>
        config.push_public_key
          ? self.registration.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: urlBase64ToUint8Array(config.push_public_key),
            })
          : null,
      )
      .then((subscription) => {
        const json = subscription?.toJSON()
        if (!json?.endpoint || !json.keys?.p256dh || !json.keys?.auth) return
        return fetch("/api/v1/notifications/subscriptions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ endpoint: json.endpoint, keys: { p256dh: json.keys.p256dh, auth: json.keys.auth } }),
        })
      })
      .catch(() => {}),
  )
})
