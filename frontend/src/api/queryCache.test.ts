// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest"

// queryCache keeps its whole state in module-level Maps (cache/inFlight/subscribers/versions/epoch),
// so every test takes a freshly evaluated copy of the module instead of trying to scrub that state
// between tests - see FRONT-TEST.md §4.1. @testing-library/react is re-imported through the same
// reset so that it and the hook under test share one React instance; importing it statically would
// leave renderHook talking to a different copy of React than useLiveQuery's hooks.
async function freshCache() {
  vi.resetModules()
  const cache = await import("./queryCache")
  const rtl = await import("@testing-library/react")
  return { ...cache, ...rtl }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

// Lets a pending .then chain run without leaning on timers.
const flush = () => new Promise((resolve) => setTimeout(resolve, 0))

describe("revalidate", () => {
  it("runs one fetch for concurrent calls on the same key", async () => {
    const { revalidate } = await freshCache()
    const fetcher = vi.fn().mockResolvedValue("value")

    const [a, b] = await Promise.all([revalidate("k", fetcher), revalidate("k", fetcher)])

    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(a).toBe("value")
    expect(b).toBe("value")
  })

  it("does not dedupe across different keys", async () => {
    const { revalidate } = await freshCache()
    const fetcher = vi.fn().mockResolvedValue("value")

    await Promise.all([revalidate("a", fetcher), revalidate("b", fetcher)])

    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it("caches the resolved value", async () => {
    const { revalidate, peekCached } = await freshCache()
    await revalidate("k", async () => "value")
    expect(peekCached("k")).toBe("value")
  })

  it("keeps an optimistic setCached instead of overwriting it with an older response", async () => {
    // Regression from 30f05c1: finishing a daily while a GET /daily was in flight used to bounce
    // the screen back to "in_progress" when the older response landed.
    const { revalidate, setCached, peekCached } = await freshCache()
    const slow = deferred<string>()

    const promise = revalidate("k", () => slow.promise)
    setCached("k", "optimistic")
    slow.resolve("stale response")

    expect(await promise).toBe("optimistic")
    expect(peekCached("k")).toBe("optimistic")
  })

  it("retries instead of resolving blind when clearCache lands mid-flight", async () => {
    // Regression from 26348b8: the version guard discarded the response without notifying anyone,
    // leaving the caller waiting on a value that would never arrive.
    const { revalidate, clearCache } = await freshCache()
    const first = deferred<string>()
    const fetcher = vi
      .fn()
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(async () => "second")

    const promise = revalidate("k", fetcher)
    clearCache()
    first.resolve("first")

    expect(await promise).toBe("second")
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it("discards a mid-flight response even on a key that never had a setCached", async () => {
    // The reason `epoch` exists on top of the per-key `versions`: with no setCached on either side
    // of the clear, this key reads as version 0 both times, so `versions` alone cannot tell the
    // stale response apart from a fresh one.
    const { revalidate, clearCache, peekCached } = await freshCache()
    const first = deferred<string>()
    const fetcher = vi
      .fn()
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(async () => "after clear")

    const promise = revalidate("never-written", fetcher)
    clearCache()
    first.resolve("before clear")

    expect(await promise).toBe("after clear")
    expect(peekCached("never-written")).toBe("after clear")
  })

  it("does not let an older call evict the in-flight entry a newer one installed", async () => {
    const { revalidate, clearCache } = await freshCache()
    const first = deferred<string>()
    const second = deferred<string>()
    const fetcherA = vi.fn(() => first.promise)
    const fetcherB = vi.fn(() => second.promise)

    const promiseA = revalidate("k", fetcherA)
    clearCache() // drops inFlight, so the next call installs its own entry
    const promiseB = revalidate("k", fetcherB)

    first.resolve("A") // the older call finishes first and must not clobber B's entry
    await flush()
    second.resolve("B")

    expect(await promiseB).toBe("B")
    expect(await promiseA).toBe("B") // A gives up its own result and joins B
    expect(fetcherA).toHaveBeenCalledTimes(1)
    expect(fetcherB).toHaveBeenCalledTimes(1)
  })

  it("propagates a rejection to the caller", async () => {
    const { revalidate } = await freshCache()
    await expect(revalidate("k", async () => Promise.reject(new Error("boom")))).rejects.toThrow(
      "boom",
    )
  })
})

describe("setCached / updateCached / peekCached", () => {
  it("hands the updater undefined for a key with nothing cached", async () => {
    const { updateCached, peekCached } = await freshCache()
    const update = vi.fn().mockReturnValue("built from scratch")

    updateCached("k", update)

    expect(update).toHaveBeenCalledWith(undefined)
    expect(peekCached("k")).toBe("built from scratch")
  })

  it("hands the updater the current value for a key that has one", async () => {
    const { setCached, updateCached, peekCached } = await freshCache()
    setCached("k", 1)
    updateCached<number>("k", (prev) => (prev ?? 0) + 1)
    expect(peekCached("k")).toBe(2)
  })

  it("never fires a fetch from peekCached", async () => {
    const { peekCached, setCached } = await freshCache()
    expect(peekCached("k")).toBeUndefined()
    setCached("k", "value")
    expect(peekCached("k")).toBe("value")
  })

  it("empties the cache on clearCache", async () => {
    const { setCached, clearCache, peekCached } = await freshCache()
    setCached("k", "value")
    clearCache()
    expect(peekCached("k")).toBeUndefined()
  })
})

describe("useLiveQuery", () => {
  it("starts loading with an empty cache and succeeds once the fetch lands", async () => {
    const { useLiveQuery, renderHook, waitFor } = await freshCache()
    const { result } = renderHook(() => useLiveQuery("k", async () => "value"))

    expect(result.current.state).toEqual({ status: "loading" })
    await waitFor(() => expect(result.current.state).toEqual({ status: "success", value: "value" }))
  })

  it("starts in success when the key is already cached", async () => {
    const { useLiveQuery, setCached, renderHook } = await freshCache()
    setCached("k", "cached")

    const { result } = renderHook(() => useLiveQuery("k", async () => "fresh"))

    expect(result.current.state).toEqual({ status: "success", value: "cached" })
  })

  it("notifies only the subscribers of the key that changed", async () => {
    const { useLiveQuery, setCached, renderHook, act, waitFor } = await freshCache()
    const a = renderHook(() => useLiveQuery("a", async () => "a1"))
    const b = renderHook(() => useLiveQuery("b", async () => "b1"))
    await waitFor(() => expect(a.result.current.state.status).toBe("success"))
    await waitFor(() => expect(b.result.current.state.status).toBe("success"))

    act(() => setCached("a", "a2"))

    expect(a.result.current.state).toEqual({ status: "success", value: "a2" })
    expect(b.result.current.state).toEqual({ status: "success", value: "b1" })
  })

  it("still hears about the optimistic value when the in-flight response is discarded", async () => {
    // The other half of 30f05c1: discarding the stale response is only safe if a mounted consumer
    // still ends up on the value that won, instead of waiting forever on a first value that is
    // never coming. Note this asserts the outcome, not the mechanism - setCached notifies the same
    // subscribers on its own way through, so the notify inside revalidate's discard branch is
    // belt-and-braces here and no test can tell the two apart.
    const env = await freshCache()
    const slow = deferred<string>()

    const { result } = env.renderHook(() => env.useLiveQuery("k", () => slow.promise))
    expect(result.current.state).toEqual({ status: "loading" })

    env.act(() => env.setCached("k", "optimistic"))
    await env.act(async () => {
      slow.resolve("stale response")
      await flush()
    })

    expect(result.current.state).toEqual({ status: "success", value: "optimistic" })
  })

  it("resets to the new key's state when the key changes", async () => {
    // The regression the hook's own comment describes: showing "rai"'s results under "mart".
    const { useLiveQuery, setCached, renderHook } = await freshCache()
    setCached("rai", "rai results")
    const slow = deferred<string>()

    const { result, rerender } = renderHook(({ key }) => useLiveQuery(key, () => slow.promise), {
      initialProps: { key: "rai" },
    })
    expect(result.current.state).toEqual({ status: "success", value: "rai results" })

    rerender({ key: "mart" })

    expect(result.current.state).toEqual({ status: "loading" })
  })

  it("keeps showing the cached value alongside an error", async () => {
    const { useLiveQuery, setCached, renderHook, waitFor } = await freshCache()
    setCached("k", "cached")

    const { result } = renderHook(() =>
      useLiveQuery("k", async () => Promise.reject(new Error("offline"))),
    )

    await waitFor(() => expect(result.current.state.status).toBe("error"))
    expect(result.current.state).toMatchObject({ status: "error", value: "cached" })
  })

  it("has no value to show when the very first fetch fails", async () => {
    const { useLiveQuery, renderHook, waitFor } = await freshCache()

    const { result } = renderHook(() =>
      useLiveQuery("k", async () => Promise.reject(new Error("offline"))),
    )

    await waitFor(() => expect(result.current.state.status).toBe("error"))
    expect(result.current.state).toMatchObject({ status: "error", value: undefined })
  })

  it("drops what it is showing and re-fetches on clearCache", async () => {
    const { useLiveQuery, clearCache, renderHook, act, waitFor } = await freshCache()
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce("first account")
      .mockResolvedValueOnce("second account")

    const { result } = renderHook(() => useLiveQuery("k", fetcher))
    await waitFor(() => expect(result.current.state).toMatchObject({ value: "first account" }))

    act(() => clearCache())

    await waitFor(() => expect(result.current.state).toMatchObject({ value: "second account" }))
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it("re-fetches on refresh even though the key is cached", async () => {
    const { useLiveQuery, renderHook, act, waitFor } = await freshCache()
    const fetcher = vi.fn().mockResolvedValueOnce("first").mockResolvedValueOnce("second")

    const { result } = renderHook(() => useLiveQuery("k", fetcher))
    await waitFor(() => expect(result.current.state).toMatchObject({ value: "first" }))

    act(() => result.current.refresh())

    await waitFor(() => expect(result.current.state).toMatchObject({ value: "second" }))
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it("unsubscribes on unmount, so a later clearCache does not wake it up", async () => {
    const { useLiveQuery, clearCache, renderHook, act, waitFor } = await freshCache()
    const fetcher = vi.fn().mockResolvedValue("value")

    const { result, unmount } = renderHook(() => useLiveQuery("k", fetcher))
    await waitFor(() => expect(result.current.state.status).toBe("success"))
    unmount()

    act(() => clearCache())
    await flush()

    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it("ignores a slow response for a key it has already moved away from", async () => {
    const { useLiveQuery, renderHook, waitFor } = await freshCache()
    const slow = deferred<string>()
    const fetchers: Record<string, () => Promise<string>> = {
      old: () => slow.promise,
      new: async () => "new value",
    }

    const { result, rerender } = renderHook(({ key }) => useLiveQuery(key, fetchers[key]), {
      initialProps: { key: "old" },
    })
    rerender({ key: "new" })
    await waitFor(() => expect(result.current.state).toMatchObject({ value: "new value" }))

    slow.resolve("old value")
    await flush()

    expect(result.current.state).toMatchObject({ value: "new value" })
  })
})
