// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

// The module keeps its whole state (cache/inFlight/controllers/subscribers plus the `active`/
// `waiting` semaphore) at module level, so every test re-imports it fresh, with
// @testing-library/react coming through the same reset - see FRONT-TEST.md §4.1.
//
// Only Date is faked, not the whole timer set: the freshness window needs a controllable clock,
// while queueMicrotask (which the StrictMode guard depends on) and waitFor's own scheduling must
// keep working for real.
const FRESH_MS = 30 * 60 * 1000
const MAX_CONCURRENT = 4
const START = new Date("2026-08-13T10:00:00Z")

interface PendingFetch {
  url: string
  signal: AbortSignal
  settled: boolean
  resolve: () => void
  respondWith: (response: unknown) => void
  reject: (error: unknown) => void
}

let pending: PendingFetch[] = []
let fetchMock: ReturnType<typeof vi.fn>
let objectUrlCounter = 0
// jsdom implements Blob but not the object-URL registry, so it is added and taken back out here
// rather than through vi.stubGlobal (which would replace the whole URL class, and jsdom's own
// internals need it to stay a constructor).
const realCreateObjectURL = URL.createObjectURL

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] })
  vi.setSystemTime(START)
  pending = []
  objectUrlCounter = 0

  // Every fetch is parked until the test settles it by hand - no timers, no real network.
  fetchMock = vi.fn(
    (url: string, init: { signal: AbortSignal }) =>
      new Promise((resolve, reject) => {
        const entry: PendingFetch = {
          url,
          signal: init.signal,
          settled: false,
          resolve: () => {
            entry.settled = true
            resolve({ ok: true, blob: async () => new Blob(["x"]) })
          },
          respondWith: (response) => {
            entry.settled = true
            resolve(response)
          },
          reject: (error) => {
            entry.settled = true
            reject(error)
          },
        }
        pending.push(entry)
      }),
  )
  vi.stubGlobal("fetch", fetchMock)
  URL.createObjectURL = vi.fn(() => `blob:${++objectUrlCounter}`)
})

afterEach(() => {
  URL.createObjectURL = realCreateObjectURL
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

async function freshEnv() {
  vi.resetModules()
  const { useQueuedThumbnail } = await import("./thumbnailQueue")
  const rtl = await import("@testing-library/react")
  return { useQueuedThumbnail, ...rtl }
}

// The still-unsettled request for a url - a revalidation is a second entry for the same url, so
// picking the first match would silently re-resolve the original (already settled) one.
function pendingFor(url: string): PendingFetch {
  const entry = pending.find((p) => p.url === url && !p.settled)
  if (!entry) throw new Error(`no in-flight fetch for ${url}`)
  return entry
}

function settleFor(url: string) {
  const entry = pendingFor(url)
  entry.resolve()
  return entry
}

describe("the concurrency cap", () => {
  it("never runs more than four fetches at once, and starts the next when a slot frees", async () => {
    const env = await freshEnv()
    const urls = ["a", "b", "c", "d", "e"]

    urls.forEach((url) => env.renderHook(() => env.useQueuedThumbnail(url)))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(MAX_CONCURRENT))

    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual(["a", "b", "c", "d"])

    await env.act(async () => {
      settleFor("a")
    })

    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(MAX_CONCURRENT + 1))
    expect(fetchMock.mock.calls.at(-1)![0]).toBe("e")
  })

  it("frees the slot again when a queued fetch fails", async () => {
    const env = await freshEnv()
    const urls = ["a", "b", "c", "d", "e"]
    urls.forEach((url) => env.renderHook(() => env.useQueuedThumbnail(url)))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(MAX_CONCURRENT))

    await env.act(async () => {
      pendingFor("a").reject(new Error("boom"))
    })

    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(MAX_CONCURRENT + 1))
  })
})

describe("sharing and caching", () => {
  it("serves two consumers of the same url from one fetch", async () => {
    const env = await freshEnv()
    const first = env.renderHook(() => env.useQueuedThumbnail("a"))
    const second = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    await env.act(async () => {
      settleFor("a")
    })

    expect(first.result.current.url).toBe("blob:1")
    expect(second.result.current.url).toBe("blob:1")
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it("serves a fresh cached entry with no network at all", async () => {
    const env = await freshEnv()
    const first = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    await env.act(async () => {
      settleFor("a")
    })
    first.unmount()

    vi.setSystemTime(new Date(START.getTime() + FRESH_MS - 1))
    const second = env.renderHook(() => env.useQueuedThumbnail("a"))

    expect(second.result.current.url).toBe("blob:1")
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it("shows a stale entry immediately and refreshes it behind the player's back", async () => {
    const env = await freshEnv()
    const first = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    await env.act(async () => {
      settleFor("a")
    })
    first.unmount()

    vi.setSystemTime(new Date(START.getTime() + FRESH_MS))
    const states: (string | null)[] = []
    const second = env.renderHook(() => {
      const state = env.useQueuedThumbnail("a")
      states.push(state.url)
      return state
    })

    expect(second.result.current.url).toBe("blob:1") // the stale copy, never a loading state
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    await env.act(async () => {
      settleFor("a")
    })

    expect(second.result.current.url).toBe("blob:2") // swapped once the new copy landed
    expect(states.filter((url) => url === null)).toHaveLength(1) // only the pre-effect first render
  })

  it("does not schedule a second revalidation while one is already running", async () => {
    const env = await freshEnv()
    const first = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    await env.act(async () => {
      settleFor("a")
    })
    first.unmount()

    vi.setSystemTime(new Date(START.getTime() + FRESH_MS))
    env.renderHook(() => env.useQueuedThumbnail("a"))
    env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    await env.act(async () => {})

    expect(fetchMock).toHaveBeenCalledTimes(2) // one original + one shared revalidation
  })
})

describe("failures", () => {
  it("reports a failed fetch as failed, with no url", async () => {
    const env = await freshEnv()
    const { result } = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    await env.act(async () => {
      pendingFor("a").reject(new Error("boom"))
    })

    expect(result.current).toEqual({ url: null, failed: true })
  })

  it("reports a non-ok response as failed", async () => {
    const env = await freshEnv()
    const { result } = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    await env.act(async () => {
      pendingFor("a").respondWith({ ok: false, status: 404 })
    })

    expect(result.current).toEqual({ url: null, failed: true })
  })

  it("keeps showing the stale copy when a background refresh fails", async () => {
    const env = await freshEnv()
    const first = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    await env.act(async () => {
      settleFor("a")
    })
    first.unmount()

    vi.setSystemTime(new Date(START.getTime() + FRESH_MS))
    const second = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))

    await env.act(async () => {
      pendingFor("a").reject(new Error("boom"))
    })

    expect(second.result.current).toEqual({ url: "blob:1", failed: false })
  })
})

describe("aborting", () => {
  it("does not abort the shared request when the same url remounts in the same tick", async () => {
    // The StrictMode regression the module's own comment describes: aborting synchronously on
    // unsubscribe poisons the in-flight request the incoming instance is about to reuse, leaving it
    // stuck on the failed placeholder.
    const env = await freshEnv()
    const first = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const signal = pending[0].signal

    let second!: ReturnType<typeof env.renderHook>
    env.act(() => {
      first.unmount()
      second = env.renderHook(() => env.useQueuedThumbnail("a"))
    })
    await env.act(async () => {})

    expect(signal.aborted).toBe(false)
    await env.act(async () => {
      settleFor("a")
    })
    expect((second.result.current as { url: string | null }).url).toBe("blob:1")
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it("aborts a genuinely orphaned request so its slot is freed", async () => {
    const env = await freshEnv()
    const first = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const signal = pending[0].signal

    first.unmount()
    await env.act(async () => {})

    expect(signal.aborted).toBe(true)
  })
})

describe("no url", () => {
  it("stays idle and never touches the network", async () => {
    const env = await freshEnv()
    const { result } = env.renderHook(() => env.useQueuedThumbnail(null))
    await env.act(async () => {})

    expect(result.current).toEqual({ url: null, failed: false })
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
