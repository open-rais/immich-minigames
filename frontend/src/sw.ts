/// <reference lib="webworker" />
export type {}
declare const self: ServiceWorkerGlobalScope

import { clientsClaim } from "workbox-core"
import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching"
import { registerRoute } from "workbox-routing"
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from "workbox-strategies"
import { ExpirationPlugin } from "workbox-expiration"
import { API_CACHE_NAME } from "./pwa/cacheNames"
import { isConfigPath, isStaticAssetPath, isThumbnailPath } from "./pwa/routeMatchers"

self.skipWaiting()
clientsClaim()

const STATIC_CACHE = "minigames-static-v1"
const SHELL_CACHE = "minigames-shell-v1"

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
    plugins: [new ExpirationPlugin({ maxEntries: 300, purgeOnQuotaError: true })],
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
