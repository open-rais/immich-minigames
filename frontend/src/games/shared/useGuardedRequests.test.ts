// @vitest-environment jsdom
import { renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { useGuardedRequests } from "./useGuardedRequests"

// No module-level state and no network here, so this one needs neither resetModules nor mocks -
// just a DOM to hang the hook off. It is the re-entrancy base of all six games.

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function inFlightRef() {
  return { current: false }
}

describe("guarded", () => {
  it("runs once when the same action fires twice before a re-render", async () => {
    // A click handler can fire twice before React re-renders, so component state can't stop the
    // second call - the ref is checked and set synchronously for exactly that reason.
    const { result } = renderHook(() => useGuardedRequests())
    const ref = inFlightRef()
    const gate = deferred<void>()
    const run = vi.fn(() => gate.promise)

    const first = result.current.guarded(ref, run)
    const second = result.current.guarded(ref, run)

    expect(run).toHaveBeenCalledTimes(1)
    gate.resolve()
    await Promise.all([first, second])
    expect(run).toHaveBeenCalledTimes(1)
  })

  it("lets independent actions run at the same time", async () => {
    // start and guess own separate refs on purpose: neither should block the other.
    const { result } = renderHook(() => useGuardedRequests())
    const startRef = inFlightRef()
    const guessRef = inFlightRef()
    const start = vi.fn(async () => {})
    const guess = vi.fn(async () => {})

    await Promise.all([
      result.current.guarded(startRef, start),
      result.current.guarded(guessRef, guess),
    ])

    expect(start).toHaveBeenCalledTimes(1)
    expect(guess).toHaveBeenCalledTimes(1)
  })

  it("releases the guard once the action settles, so the next click works", async () => {
    const { result } = renderHook(() => useGuardedRequests())
    const ref = inFlightRef()
    const run = vi.fn(async () => {})

    await result.current.guarded(ref, run)
    await result.current.guarded(ref, run)

    expect(run).toHaveBeenCalledTimes(2)
    expect(ref.current).toBe(false)
  })

  it("releases the guard even when the action throws", async () => {
    const { result } = renderHook(() => useGuardedRequests())
    const ref = inFlightRef()

    await expect(
      result.current.guarded(ref, async () => {
        throw new Error("boom")
      }),
    ).rejects.toThrow("boom")

    expect(ref.current).toBe(false)
  })
})

describe("token staleness", () => {
  it("keeps a token current while nothing else happens", async () => {
    const { result } = renderHook(() => useGuardedRequests())
    let seen: boolean | undefined

    await result.current.guarded(inFlightRef(), async (token) => {
      seen = result.current.isCurrent(token)
    })

    expect(seen).toBe(true)
  })

  it("invalidates the in-flight token when the player backs out", async () => {
    const { result } = renderHook(() => useGuardedRequests())
    const gate = deferred<void>()
    let token = -1

    const running = result.current.guarded(inFlightRef(), async (t) => {
      token = t
      await gate.promise
    })
    result.current.discardInFlight()
    gate.resolve()
    await running

    expect(result.current.isCurrent(token)).toBe(false)
  })

  it("invalidates the previous action's token when a new one starts", async () => {
    // Shared token across every guarded() call in a component: hitting Back while a guess is in
    // flight also has to invalidate a start that raced in behind it.
    const { result } = renderHook(() => useGuardedRequests())
    const first = deferred<void>()
    let firstToken = -1

    const firstRun = result.current.guarded(inFlightRef(), async (t) => {
      firstToken = t
      await first.promise
    })
    await result.current.guarded(inFlightRef(), async () => {})

    expect(result.current.isCurrent(firstToken)).toBe(false)
    first.resolve()
    await firstRun
  })
})
