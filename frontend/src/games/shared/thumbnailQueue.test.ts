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
// Mirrored from games/shared/imageLoading.ts, same as MAX_CONCURRENT is mirrored from the module
// under test - importing them would tie these tests to the very module they are pinning down.
const IMAGE_TIMEOUT_MS = 8_000
const MAX_IMAGE_ATTEMPTS = 3
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
        // A real fetch rejects with AbortError when its signal fires; the queue's timeout depends
        // on that, so the mock has to do it too rather than staying pending forever.
        init.signal.addEventListener("abort", () => {
          if (entry.settled) return
          entry.settled = true
          reject(new DOMException("aborted", "AbortError"))
        })
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
  const { useQueuedThumbnail, prefetchThumbnail } = await import("./thumbnailQueue")
  const rtl = await import("@testing-library/react")
  return { useQueuedThumbnail, prefetchThumbnail, ...rtl }
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

// Fails `url` as many times as the retry budget allows, which is what it takes for the hook to
// report `failed` - anything less is retried silently.
async function exhaustAttempts(env: Awaited<ReturnType<typeof freshEnv>>, url: string) {
  for (let i = 0; i < MAX_IMAGE_ATTEMPTS; i++) {
    await env.act(async () => {
      pendingFor(url).reject(new Error("boom"))
    })
  }
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
  it("reports a failed fetch as failed, with no url, once the retries are spent", async () => {
    const env = await freshEnv()
    const { result } = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    await exhaustAttempts(env, "a")

    expect(result.current).toMatchObject({ url: null, failed: true })
  })

  it("retries silently before reporting anything to the caller", async () => {
    const env = await freshEnv()
    const { result } = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    for (let attempt = 1; attempt < MAX_IMAGE_ATTEMPTS; attempt++) {
      await env.act(async () => {
        pendingFor("a").reject(new Error("boom"))
      })
      // Still "loading" as far as the caller is concerned - it must not flash a broken photo for
      // something that is about to succeed on the next attempt.
      expect(result.current.failed).toBe(false)
      expect(fetchMock).toHaveBeenCalledTimes(attempt + 1)
    }

    await env.act(async () => {
      settleFor("a")
    })

    expect(result.current.url).toBe("blob:1")
  })

  it("reports a non-ok response as failed", async () => {
    const env = await freshEnv()
    const { result } = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    for (let i = 0; i < MAX_IMAGE_ATTEMPTS; i++) {
      await env.act(async () => {
        pendingFor("a").respondWith({ ok: false, status: 404 })
      })
    }

    expect(result.current).toMatchObject({ url: null, failed: true })
  })

  it("retry() starts over with a fresh budget after the automatic ones ran out", async () => {
    const env = await freshEnv()
    const { result } = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    await exhaustAttempts(env, "a")
    expect(result.current.failed).toBe(true)

    await env.act(async () => {
      result.current.retry()
    })
    expect(fetchMock).toHaveBeenCalledTimes(MAX_IMAGE_ATTEMPTS + 1)

    await env.act(async () => {
      settleFor("a")
    })

    expect(result.current).toMatchObject({ url: "blob:1", failed: false })
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

    expect(second.result.current).toMatchObject({ url: "blob:1", failed: false })
  })
})

describe("the network timeout", () => {
  // The only block that fakes setTimeout - the rest of the file deliberately doesn't (see the
  // header), so the timeout has to be exercised on its own, without waitFor's real scheduling.
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date", "setTimeout", "clearTimeout"] })
    vi.setSystemTime(START)
  })

  it("aborts a stalled fetch instead of letting it hold its slot forever", async () => {
    const env = await freshEnv()
    const urls = ["a", "b", "c", "d", "e"]
    urls.forEach((url) => env.renderHook(() => env.useQueuedThumbnail(url)))
    await env.act(async () => {})

    // "e" is queued behind the four running requests, none of which will ever answer.
    expect(fetchMock).toHaveBeenCalledTimes(MAX_CONCURRENT)
    expect(pendingFor("a").signal.aborted).toBe(false)

    await env.act(async () => {
      vi.advanceTimersByTime(IMAGE_TIMEOUT_MS)
    })

    // Before the timeout existed this was the permanent deadlock: four stalled requests and every
    // later thumbnail in the session waiting on a slot that never came back.
    expect(fetchMock.mock.calls.map((call) => call[0])).toContain("e")
  })

  it("does not abort a fetch that answered in time", async () => {
    const env = await freshEnv()
    const { result } = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.act(async () => {})
    const entry = pendingFor("a")

    await env.act(async () => {
      entry.resolve()
    })
    await env.act(async () => {
      vi.advanceTimersByTime(IMAGE_TIMEOUT_MS * 2)
    })

    expect(entry.signal.aborted).toBe(false)
    expect(result.current.url).toBe("blob:1")
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

    expect(result.current).toMatchObject({ url: null, failed: false })
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe("prefetchThumbnail", () => {
  it("fetches an uncached url", async () => {
    const env = await freshEnv()
    env.prefetchThumbnail("a")

    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(fetchMock.mock.calls[0][0]).toBe("a")
  })

  it("does nothing for a url already resolved in cache", async () => {
    const env = await freshEnv()
    const first = env.renderHook(() => env.useQueuedThumbnail("a"))
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    await env.act(async () => {
      settleFor("a")
    })
    first.unmount()

    env.prefetchThumbnail("a")
    await env.act(async () => {})

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it("does not throw or leave an unhandled rejection when the fetch fails", async () => {
    const env = await freshEnv()
    env.prefetchThumbnail("a")
    await env.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    await env.act(async () => {
      pendingFor("a").reject(new Error("boom"))
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
