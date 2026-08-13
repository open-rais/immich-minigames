import { useEffect, useState } from "react"

// Matches the browser's own per-host HTTP/1.1 concurrency limit - generous for what Immich needs
// to serve, while still capping how many requests this app can pile onto the backend at once.
const MAX_CONCURRENT = 4

// Within this window, a resolved thumbnail is served straight from cache with no network activity
// at all. Past it, the stale copy is still shown immediately (never a loading state for something
// already seen this session) while a background refetch silently brings the cache up to date.
const FRESH_MS = 30 * 60 * 1000

let active = 0
const waiting: Array<() => void> = []

function acquire(): Promise<void> {
  if (active < MAX_CONCURRENT) {
    active++
    return Promise.resolve()
  }
  return new Promise((resolve) => waiting.push(resolve))
}

function release(): void {
  const next = waiting.shift()
  if (next) {
    next()
  } else {
    active--
  }
}

interface CacheEntry {
  objectUrl: string
  fetchedAt: number
}

// Resolved entries are cached forever (module-level singleton) and object URLs are never revoked,
// including ones replaced by a later revalidation - acceptable for this fix's scope,
// a long-lived session growing this cache unbounded is a problem for another day.
const cache = new Map<string, CacheEntry>()
const inFlight = new Map<string, Promise<CacheEntry>>()
const controllers = new Map<string, AbortController>()
const subscribers = new Map<string, Set<(entry: CacheEntry) => void>>()

async function fetchQueued(url: string, signal: AbortSignal): Promise<CacheEntry> {
  await acquire()
  try {
    if (signal.aborted) {
      throw new DOMException("aborted", "AbortError")
    }
    const response = await fetch(url, { credentials: "same-origin", signal })
    if (!response.ok) {
      throw new Error(`thumbnail fetch failed: ${response.status}`)
    }
    const blob = await response.blob()
    return { objectUrl: URL.createObjectURL(blob), fetchedAt: Date.now() }
  } finally {
    release()
  }
}

function notify(url: string, entry: CacheEntry): void {
  for (const listener of subscribers.get(url) ?? []) {
    listener(entry)
  }
}

// Starts (or joins, if already running) the fetch for `url`. Resolves/rejects for every caller
// sharing the same in-flight request, and additionally pushes successful results to anyone
// subscribed via `subscribe` below - the latter is what lets a background revalidation update
// components that are already mounted and showing the stale entry.
function getQueuedThumbnail(url: string): Promise<CacheEntry> {
  let promise = inFlight.get(url)
  if (!promise) {
    const controller = new AbortController()
    controllers.set(url, controller)
    promise = fetchQueued(url, controller.signal)
      .then((entry) => {
        cache.set(url, entry)
        notify(url, entry)
        return entry
      })
      .finally(() => {
        inFlight.delete(url)
        controllers.delete(url)
      })
    inFlight.set(url, promise)
  }
  return promise
}

// Fire-and-forget background refresh of an already-cached, stale entry. A no-op if one is already
// running (the initial fetch, or a previous revalidation still in flight) - `getQueuedThumbnail`'s
// dedupe covers that, this just avoids scheduling a redundant call.
function revalidate(url: string): void {
  if (inFlight.has(url)) {
    return
  }
  getQueuedThumbnail(url).catch(() => {
    // The consumer already has the stale entry on screen - a failed background refresh isn't worth
    // surfacing as a new failure state, it'll just retry next time the component (re)subscribes.
  })
}

function subscribe(url: string, listener: (entry: CacheEntry) => void): void {
  let set = subscribers.get(url)
  if (!set) {
    set = new Set()
    subscribers.set(url, set)
  }
  set.add(listener)
}

function unsubscribe(url: string, listener: (entry: CacheEntry) => void): void {
  const set = subscribers.get(url)
  if (!set) {
    return
  }
  set.delete(listener)
  if (set.size > 0) {
    return
  }
  subscribers.delete(url)
  // No one left waiting on this URL *right now* - but don't abort synchronously: React StrictMode
  // (and fast remounts in general) can unsubscribe the outgoing instance and subscribe the incoming
  // one for the same URL back-to-back in the same tick, and a synchronous abort() here would poison
  // the shared in-flight request before the new subscriber's own call ever gets a chance to reuse it
  // (the request would still complete over the network - hence a stray 304 in devtools - but reject
  // on our side with AbortError, leaving the new subscriber stuck on the failed placeholder).
  // Deferring one microtask lets that resubscribe happen first; if the URL is genuinely orphaned by
  // the time this runs, abort it so it stops occupying a concurrency slot other screens need.
  queueMicrotask(() => {
    if (!subscribers.has(url)) {
      controllers.get(url)?.abort()
    }
  })
}

interface QueuedThumbnail {
  url: string | null
  failed: boolean
}

const IDLE: QueuedThumbnail = { url: null, failed: false }

// Fetches `url` through the dedupe+concurrency queue above instead of letting an `<img src>` hit
// the network directly - that's the only way a fixed concurrency cap can actually apply, since a
// plain `<img>` fires its request immediately, with no chance for a semaphore to hold it back.
//
// Returns `{ url: null, failed: false }` while waiting on a first-ever fetch - the caller keeps
// showing its existing loading placeholder. Once cached (fresh or stale), `url` is an object URL
// ready to use as `src` immediately, and stays that way even while a stale entry silently
// revalidates in the background - the caller only ever sees the swap once a newer copy lands, never
// a loading state for something it's already shown once this session. On failure, `failed` is
// true - a fetch error never reaches an `<img onError>` (the `<img>` isn't the one making the
// request), so this is the only way the caller's own failed-placeholder state can find out; wire it
// in directly instead of an `onError` handler.
export function useQueuedThumbnail(url: string | null): QueuedThumbnail {
  const [state, setState] = useState<QueuedThumbnail>(IDLE)

  useEffect(() => {
    setState(IDLE)
    if (!url) {
      return
    }

    let cancelled = false
    const applyEntry = (entry: CacheEntry) => {
      if (!cancelled) {
        setState({ url: entry.objectUrl, failed: false })
      }
    }
    subscribe(url, applyEntry)

    const existing = cache.get(url)
    if (existing) {
      applyEntry(existing)
      if (Date.now() - existing.fetchedAt >= FRESH_MS) {
        revalidate(url)
      }
    } else {
      getQueuedThumbnail(url).catch(() => {
        if (!cancelled) {
          setState({ url: null, failed: true })
        }
      })
    }

    return () => {
      cancelled = true
      unsubscribe(url, applyEntry)
    }
  }, [url])

  return state
}
