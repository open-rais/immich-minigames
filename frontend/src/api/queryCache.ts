import { useEffect, useRef, useState } from "react"

// Generic "show cached now, always ask" query cache - see docs/TODO/CACHE.md §3 for the design
// rationale (deliberately not TTL/stale-while-revalidate like thumbnailQueue.ts: these are small
// JSON values that change from real user actions while the app is open, not near-immutable image
// blobs).
const cache = new Map<string, unknown>()
const inFlight = new Map<string, Promise<unknown>>()
const subscribers = new Map<string, Set<(value: unknown) => void>>()
// Bumped on every setCached() for a key. A revalidation that started BEFORE the latest setCached
// discards its own result instead of clobbering the optimistic value with a stale one - without
// this, finishing a daily while a GET /daily is in flight would bounce the screen back to
// "in_progress" once that response lands.
const versions = new Map<string, number>()

// Always fires a real request (deduped only if one is already in flight for the same key - never
// skipped for being "still fresh", that doesn't exist in this design). On resolve, updates the
// cache and notifies every subscriber of that key, including the caller.
export function revalidate<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const existing = inFlight.get(key)
  if (existing) return existing as Promise<T>

  const startedAt = versions.get(key) ?? 0
  const promise = fetcher()
    .then((value) => {
      if ((versions.get(key) ?? 0) !== startedAt) return cache.get(key) as T
      cache.set(key, value)
      subscribers.get(key)?.forEach((notify) => notify(value))
      return value
    })
    .finally(() => inFlight.delete(key))
  inFlight.set(key, promise)
  return promise
}

// For when the user's own action just changed the data (finished a daily, beat their record,
// saved an admin setting) - immediate optimistic update, without waiting for even the round trip
// of a normal revalidation.
export function setCached<T>(key: string, value: T): void {
  versions.set(key, (versions.get(key) ?? 0) + 1)
  cache.set(key, value)
  subscribers.get(key)?.forEach((notify) => notify(value))
}

// Read-modify-write over what's already cached: needed when a key's value is a collection and
// only one entry changed (e.g. "game-records" caches the whole response, not a loose record, so
// plain setCached isn't enough).
export function updateCached<T>(key: string, update: (prev: T | undefined) => T): void {
  setCached(key, update(cache.get(key) as T | undefined))
}

// Non-subscribing read of whatever is currently cached for a key, for callers that need to decide
// *whether* to write (e.g. "is this score actually higher than the cached best?") without mounting
// a useLiveQuery subscription (which would fire a real, unwanted request every time).
export function peekCached<T>(key: string): T | undefined {
  return cache.get(key) as T | undefined
}

// Clears everything. AuthProvider calls this on login/register/logout - the in-memory cache is
// scoped to the tab, not the session, so without this a second account signing in on the same tab
// would briefly see the previous account's cached data.
export function clearCache(): void {
  cache.clear()
  inFlight.clear()
  versions.clear()
}

interface LiveQuery<T> {
  value: T | undefined
  // Doesn't swallow errors: callers like AdminGamesSection show a real error message and still
  // need to. If there was already a cached value it stays shown *alongside* the error - the caller
  // decides what to do with that combination.
  error: unknown
  refresh: () => void
}

// Consumption hook: returns whatever is cached up front (undefined the very first time, in which
// case the caller keeps showing its current placeholder - same pattern as useQueuedThumbnail), and
// subscribes to future updates of that key regardless of who triggers them.
export function useLiveQuery<T>(key: string, fetcher: () => Promise<T>): LiveQuery<T> {
  const [value, setValue] = useState<T | undefined>(() => cache.get(key) as T | undefined)
  const [error, setError] = useState<unknown>(null)
  const [nonce, setNonce] = useState(0)

  // The fetcher is re-created on every render; keeping it in a ref avoids listing it as an effect
  // dependency (which would re-run it - and hit the network - on every render).
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    // Required: useState's initializer only runs once, so without this a key change keeps showing
    // the previous key's value until the new response arrives (in the person-search case, that's
    // showing "rai"'s results under the newly typed "mart").
    setValue(cache.get(key) as T | undefined)
    setError(null)

    let cancelled = false
    const set = subscribers.get(key) ?? new Set<(value: unknown) => void>()
    subscribers.set(key, set)
    const callback = (v: unknown) => setValue(v as T)
    set.add(callback)

    // The `cancelled` guard is still needed even though subscribers are cleaned up below: this
    // continuation is direct, not routed through pub-sub, so without it a slow response for an old
    // key would clobber the new key's state.
    revalidate(key, fetcherRef.current).then(
      (v) => {
        if (!cancelled) setValue(v)
      },
      (e) => {
        if (!cancelled) setError(e)
      },
    )

    return () => {
      cancelled = true
      set.delete(callback)
    }
  }, [key, nonce])

  return { value, error, refresh: () => setNonce((n) => n + 1) }
}
