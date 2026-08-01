import { useEffect, useState } from "react"

// Mitigation for issue #44 (docs/TODO/ISSUE-SUMMARY-PAGE.md §3.3) - "Ver rondas" screens render
// every round's thumbnail at once, which used to fire one request per entry with no limit and no
// dedupe, exhausting the backend's DB connection pool. This module gives those screens a shared
// dedupe cache + concurrency cap; scoping it to "Ver rondas" only (not live play) happens at the
// call site (F3), not here - this module doesn't know who's calling it.

// Matches the browser's own per-host HTTP/1.1 concurrency limit - generous for what Immich needs
// to serve, while still capping how many requests this app can pile onto the backend at once.
const MAX_CONCURRENT = 4

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

// Resolved URLs are cached forever (module-level singleton) and object URLs are never revoked -
// acceptable for this fix's scope (docs/TODO/ISSUE-SUMMARY-PAGE.md §4), a long-lived session
// growing this cache unbounded is a problem for another day.
const cache = new Map<string, Promise<string>>()

async function fetchQueued(url: string): Promise<string> {
  await acquire()
  try {
    const response = await fetch(url, { credentials: "same-origin" })
    if (!response.ok) {
      throw new Error(`thumbnail fetch failed: ${response.status}`)
    }
    const blob = await response.blob()
    return URL.createObjectURL(blob)
  } finally {
    release()
  }
}

function getQueuedThumbnail(url: string): Promise<string> {
  let promise = cache.get(url)
  if (!promise) {
    promise = fetchQueued(url).catch((err: unknown) => {
      // Don't poison the cache with a permanent failure - a later remount (or the backend
      // recovering) should get to retry instead of being stuck failed forever.
      cache.delete(url)
      throw err
    })
    cache.set(url, promise)
  }
  return promise
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
// Returns `{ url: null, failed: false }` while waiting - the caller keeps showing its existing
// loading placeholder. On success, `url` is an object URL ready to use as `src`. On failure,
// `failed` is true - a fetch error never reaches an `<img onError>` (the `<img>` isn't the one
// making the request), so this is the only way the caller's own failed-placeholder state can find
// out; wire it in directly instead of an `onError` handler.
export function useQueuedThumbnail(url: string | null): QueuedThumbnail {
  const [state, setState] = useState<QueuedThumbnail>(IDLE)

  useEffect(() => {
    setState(IDLE)
    if (!url) {
      return
    }
    let cancelled = false
    getQueuedThumbnail(url)
      .then((objectUrl) => {
        if (!cancelled) {
          setState({ url: objectUrl, failed: false })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState({ url: null, failed: true })
        }
      })
    return () => {
      cancelled = true
    }
  }, [url])

  return state
}
