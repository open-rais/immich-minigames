import { API_CACHE_NAME } from "./cacheNames"

// Cache Storage is per-origin, not per-session: without this, thumbnails cached by account A on a
// shared browser would keep being served to account B after they log in. Best-effort - a failure
// here must never block logout itself.
export function clearApiCache(): void {
  if (!("caches" in window)) return
  caches.delete(API_CACHE_NAME).catch((error: unknown) => {
    console.error("Failed to clear API cache on logout", error)
  })
}
