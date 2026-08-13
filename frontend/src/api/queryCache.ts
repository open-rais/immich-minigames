import { useEffect, useRef, useState } from "react"

// Generic "show cached now, always ask" query cache.
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
  // Typed explicitly: the `.then` below closes over `promise` itself (to check it's still the
  // in-flight entry before deleting it), which would otherwise make its own type circular.
  const promise: Promise<T> = fetcher()
    .then((value) => {
      if ((versions.get(key) ?? 0) !== startedAt) {
        const current = cache.get(key)
        if (current !== undefined) {
          // A newer setCached() landed while this was in flight - don't clobber it, but still
          // notify every subscriber (not just this call's own awaiter) so nobody is left waiting
          // on a first value that will never arrive.
          subscribers.get(key)?.forEach((notify) => notify(current))
          return current as T
        }
        // Nothing safe to serve (e.g. clearCache() ran mid-flight) - resolving to undefined here
        // would be indistinguishable from "still loading" forever. Retry
        // instead of resolving blind; useLiveQuery never has to know this happened. Only clear
        // inFlight if it's still pointing at this call - otherwise the retry below has already
        // replaced it with its own, newer entry.
        if (inFlight.get(key) === promise) inFlight.delete(key)
        return revalidate(key, fetcher)
      }
      cache.set(key, value)
      subscribers.get(key)?.forEach((notify) => notify(value))
      return value
    })
    .finally(() => {
      // Same identity check as above: a slower, older call finishing after a newer one has
      // already taken over this key must not evict the newer one's still-pending entry.
      if (inFlight.get(key) === promise) inFlight.delete(key)
    })
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

// "loading" is genuinely transitory: revalidate() above never resolves successfully without a
// real value (it retries itself rather than doing that), so it always ends in "success" or
// "error" - there's no fourth "discarded" state for callers to have to think about. Doesn't
// swallow errors: callers like AdminGamesSection show a real error message and still need to. If
// there was already a cached value it stays shown *alongside* the error - the caller decides what
// to do with that combination.
export type QueryState<T> =
  | { status: "loading" }
  | { status: "success"; value: T }
  | { status: "error"; error: unknown; value?: T }

interface LiveQuery<T> {
  state: QueryState<T>
  refresh: () => void
}

function stateFromCache<T>(key: string): QueryState<T> {
  const cached = cache.get(key) as T | undefined
  return cached !== undefined ? { status: "success", value: cached } : { status: "loading" }
}

// Consumption hook: returns whatever is cached up front (still "loading" the very first time, in
// which case the caller keeps showing its current placeholder - same pattern as
// useQueuedThumbnail), and subscribes to future updates of that key regardless of who triggers
// them.
export function useLiveQuery<T>(key: string, fetcher: () => Promise<T>): LiveQuery<T> {
  const [state, setState] = useState<QueryState<T>>(() => stateFromCache(key))
  const [nonce, setNonce] = useState(0)

  // The fetcher is re-created on every render; keeping it in a ref avoids listing it as an effect
  // dependency (which would re-run it - and hit the network - on every render).
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    // Required: useState's initializer only runs once, so without this a key change keeps showing
    // the previous key's value until the new response arrives (in the person-search case, that's
    // showing "rai"'s results under the newly typed "mart").
    setState(stateFromCache(key))

    let cancelled = false
    const set = subscribers.get(key) ?? new Set<(value: unknown) => void>()
    subscribers.set(key, set)
    const callback = (v: unknown) => setState({ status: "success", value: v as T })
    set.add(callback)

    // The `cancelled` guard is still needed even though subscribers are cleaned up below: this
    // continuation is direct, not routed through pub-sub, so without it a slow response for an old
    // key would clobber the new key's state.
    revalidate(key, fetcherRef.current).then(
      (v) => {
        if (!cancelled) setState({ status: "success", value: v as T })
      },
      (e) => {
        // Functional update so a value that arrived via the subscriber callback above (or was
        // already cached) between this effect starting and the fetch rejecting stays visible
        // alongside the error, instead of this overwriting it with a bare error.
        if (!cancelled) {
          setState((prev) => ({
            status: "error",
            error: e,
            value: prev.status === "loading" ? undefined : prev.value,
          }))
        }
      },
    )

    return () => {
      cancelled = true
      set.delete(callback)
    }
  }, [key, nonce])

  return { state, refresh: () => setNonce((n) => n + 1) }
}
