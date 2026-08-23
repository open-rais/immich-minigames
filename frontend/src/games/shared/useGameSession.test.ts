// @vitest-environment jsdom
import { AxiosError, AxiosHeaders } from "axios"
import type { AxiosResponse } from "axios"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"
import type { GameOut } from "../../api/types/common"
import type { DailyModeStatusOut, DailyStatusOut } from "../../api/types/daily"

// Only the typed request functions are mocked, never axios or the network itself (FRONT-TEST.md
// §6.1). api/errors.ts stays real, because the 409 fallback below is exactly its job.
vi.mock("../../api/daily", () => ({
  getDailyStatus: vi.fn(),
  createDailyGame: vi.fn(),
}))
vi.mock("../../api/games", () => ({
  getCurrentGame: vi.fn(),
  createGame: vi.fn(),
  getGame: vi.fn(),
  GAME_RECORDS_KEY: "game-records",
}))

const GAME_TYPE = "timeline"
const MODE = "arcade"

// Fresh module registry per test: useGameSession reads and writes queryCache's module-level state,
// and @testing-library/react has to come through the same reset so it shares one React instance
// with the hook under test - see FRONT-TEST.md §4.1.
async function freshEnv() {
  vi.resetModules()
  const daily = await import("../../api/daily")
  const games = await import("../../api/games")
  const queryCache = await import("../../api/queryCache")
  const { useGameSession, DAILY_STATUS_KEY } = await import("./useGameSession")
  const { DailyFinishedContext } = await import("./dailyFinishedContext")
  // Same registry as the hook and as @testing-library/react - a React imported from the outer
  // registry would be a second copy, and the provider below wouldn't reach the hook at all.
  const react = await import("react")
  const rtl = await import("@testing-library/react")
  return {
    DailyFinishedContext,
    react,
    getDailyStatus: vi.mocked(daily.getDailyStatus),
    createDailyGame: vi.mocked(daily.createDailyGame),
    getCurrentGame: vi.mocked(games.getCurrentGame),
    createGame: vi.mocked(games.createGame),
    getGame: vi.mocked(games.getGame),
    queryCache,
    useGameSession,
    DAILY_STATUS_KEY,
    ...rtl,
  }
}

function gameOut(overrides: Partial<GameOut> = {}): GameOut {
  return {
    id: "g1",
    type: GAME_TYPE,
    mode: MODE,
    score: 0,
    finished: false,
    rounds: [],
    ...overrides,
  }
}

function modeStatus(overrides: Partial<DailyModeStatusOut> = {}): DailyModeStatusOut {
  return {
    game_type: GAME_TYPE,
    mode: MODE,
    status: "not_played",
    game_id: null,
    score: null,
    ...overrides,
  }
}

function dailyStatus(modes: DailyModeStatusOut[]): DailyStatusOut {
  return { resets_at: "2026-08-14T00:00:00Z", server_now: "2026-08-13T10:00:00Z", modes }
}

function conflictError(): AxiosError {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError("conflict", "ERR_BAD_REQUEST", config, {}, {
    status: 409,
    statusText: "Conflict",
    data: { detail: "already played today" },
    headers: {},
    config,
  } as AxiosResponse)
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

const flush = () => new Promise((resolve) => setTimeout(resolve, 0))

type SessionConfig = Parameters<
  Awaited<ReturnType<typeof freshEnv>>["useGameSession"]
>[0] extends infer C
  ? C
  : never

function config(overrides: Partial<SessionConfig> = {}) {
  return {
    gameType: GAME_TYPE,
    mode: MODE,
    applyGame: vi.fn().mockReturnValue(true),
    hydrateFinishedDaily: vi.fn().mockReturnValue(true),
    ...overrides,
  }
}

describe("the non-daily idle check", () => {
  it("asks once for an existing game and reports that there is one", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(gameOut())

    const { result } = env.renderHook(() => env.useGameSession(config()))

    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(true))
    expect(env.getCurrentGame).toHaveBeenCalledTimes(1)
    expect(env.getCurrentGame).toHaveBeenCalledWith(GAME_TYPE, MODE)
  })

  it("reports no game when the lookup comes back empty", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)

    const { result } = env.renderHook(() => env.useGameSession(config()))

    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))
  })

  it("settles on false rather than staying unknown when the lookup fails", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockRejectedValue(new Error("offline"))

    const { result } = env.renderHook(() => env.useGameSession(config()))

    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))
    expect(result.current.screen).toBe("idle")
  })

  it("never touches the daily status endpoint", async () => {
    // The reason INACTIVE_DAILY_STATUS_KEY exists: Rules of Hooks force the useLiveQuery call to
    // happen either way, so a non-daily game must be pointed at a fetcher that isn't the network.
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)

    const { result } = env.renderHook(() => env.useGameSession(config()))
    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))

    expect(env.getDailyStatus).not.toHaveBeenCalled()
  })
})

describe("the daily idle check", () => {
  it("jumps a finished daily straight to the finished screen", async () => {
    const env = await freshEnv()
    const cfg = config({ daily: true })
    env.getDailyStatus.mockResolvedValue(
      dailyStatus([modeStatus({ status: "finished", game_id: "g9", score: 42 })]),
    )
    env.getGame.mockResolvedValue(gameOut({ id: "g9", finished: true, score: 42 }))

    const { result } = env.renderHook(() => env.useGameSession(cfg))

    await env.waitFor(() => expect(result.current.screen).toBe("finished"))
    expect(env.getGame).toHaveBeenCalledWith("g9")
    expect(cfg.hydrateFinishedDaily).toHaveBeenCalledTimes(1)
    expect(result.current.hasCurrentGame).toBe(false)
  })

  it("never releases the blank guard before the finished screen is ready", async () => {
    // The stutter documented at useGameSession.ts's finished-daily branch: hasCurrentGame must go
    // null -> false in the same dispatch as the screen change, never while the screen is still idle,
    // or the game component's `daily && hasCurrentGame === null` guard lifts and flashes the idle
    // screen for a frame.
    const env = await freshEnv()
    const snapshots: { screen: string; hasCurrentGame: boolean | null }[] = []
    env.getDailyStatus.mockResolvedValue(
      dailyStatus([modeStatus({ status: "finished", game_id: "g9" })]),
    )
    env.getGame.mockResolvedValue(gameOut({ id: "g9", finished: true }))

    const { result } = env.renderHook(() => {
      const session = env.useGameSession(config({ daily: true }))
      snapshots.push({ screen: session.screen, hasCurrentGame: session.hasCurrentGame })
      return session
    })
    await env.waitFor(() => expect(result.current.screen).toBe("finished"))

    expect(snapshots.filter((s) => s.screen === "idle" && s.hasCurrentGame !== null)).toEqual([])
  })

  it("shows the error screen when the finished daily cannot be loaded", async () => {
    const env = await freshEnv()
    env.getDailyStatus.mockResolvedValue(
      dailyStatus([modeStatus({ status: "finished", game_id: "g9" })]),
    )
    env.getGame.mockRejectedValue(new Error("offline"))

    const { result } = env.renderHook(() => env.useGameSession(config({ daily: true })))

    await env.waitFor(() => expect(result.current.screen).toBe("error"))
    expect(result.current.hasCurrentGame).toBe(false)
  })

  it("shows the error screen when hydrating the finished daily fails", async () => {
    const env = await freshEnv()
    const cfg = config({ daily: true, hydrateFinishedDaily: vi.fn().mockReturnValue(false) })
    env.getDailyStatus.mockResolvedValue(
      dailyStatus([modeStatus({ status: "finished", game_id: "g9" })]),
    )
    env.getGame.mockResolvedValue(gameOut({ id: "g9", finished: true }))

    const { result } = env.renderHook(() => env.useGameSession(cfg))

    await env.waitFor(() => expect(result.current.screen).toBe("error"))
  })

  it("offers to resume an in-progress daily by its known id, never via getCurrentGame", async () => {
    const env = await freshEnv()
    const cfg = config({ daily: true })
    env.getDailyStatus.mockResolvedValue(
      dailyStatus([modeStatus({ status: "in_progress", game_id: "g7" })]),
    )
    env.getGame.mockResolvedValue(gameOut({ id: "g7" }))

    const { result } = env.renderHook(() => env.useGameSession(cfg))
    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(true))

    await env.act(() => result.current.resumeGame())

    expect(env.getGame).toHaveBeenCalledWith("g7")
    expect(env.getCurrentGame).not.toHaveBeenCalled()
    expect(cfg.applyGame).toHaveBeenCalledWith(expect.objectContaining({ id: "g7" }), true)
    expect(result.current.screen).toBe("playing")
  })

  it("reports no game when this mode has not been played today", async () => {
    const env = await freshEnv()
    env.getDailyStatus.mockResolvedValue(dailyStatus([modeStatus({ status: "not_played" })]))

    const { result } = env.renderHook(() => env.useGameSession(config({ daily: true })))

    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))
  })

  it("settles on false when the status request fails outright", async () => {
    const env = await freshEnv()
    env.getDailyStatus.mockRejectedValue(new Error("offline"))

    const { result } = env.renderHook(() => env.useGameSession(config({ daily: true })))

    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))
  })
})

describe("startGame", () => {
  it("moves to the playing screen and clears busy on the happy path", async () => {
    const env = await freshEnv()
    const cfg = config()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut())

    const { result } = env.renderHook(() => env.useGameSession(cfg))
    await env.act(() => result.current.startGame())

    expect(result.current.screen).toBe("playing")
    expect(result.current.busy).toBe(false)
    expect(cfg.applyGame).toHaveBeenCalledWith(expect.objectContaining({ id: "g1" }), false)
  })

  it("shows the error screen when the game cannot be applied", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut())

    const { result } = env.renderHook(() =>
      env.useGameSession(config({ applyGame: vi.fn().mockReturnValue(false) })),
    )
    await env.act(() => result.current.startGame())

    expect(result.current.screen).toBe("error")
  })

  it("clears busy on the error path too", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockRejectedValue(new Error("offline"))

    const { result } = env.renderHook(() => env.useGameSession(config()))
    await env.act(() => result.current.startGame())

    expect(result.current.screen).toBe("error")
    expect(result.current.busy).toBe(false)
  })

  it("creates a daily game through the daily endpoint", async () => {
    const env = await freshEnv()
    env.getDailyStatus.mockResolvedValue(dailyStatus([modeStatus()]))
    env.createDailyGame.mockResolvedValue(gameOut())

    const { result } = env.renderHook(() => env.useGameSession(config({ daily: true })))
    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))
    await env.act(() => result.current.startGame())

    expect(env.createDailyGame).toHaveBeenCalledWith(GAME_TYPE, MODE)
    expect(env.createGame).not.toHaveBeenCalled()
    expect(result.current.screen).toBe("playing")
  })

  it("falls back to a fresh status check when today's attempt was already consumed", async () => {
    // 409 from another tab/device: this is a state ("already played today"), not an error screen.
    const env = await freshEnv()
    env.getDailyStatus.mockResolvedValueOnce(dailyStatus([modeStatus()]))
    env.createDailyGame.mockRejectedValue(conflictError())
    env.getDailyStatus.mockResolvedValueOnce(
      dailyStatus([modeStatus({ status: "finished", game_id: "g9", score: 10 })]),
    )
    env.getGame.mockResolvedValue(gameOut({ id: "g9", finished: true, score: 10 }))

    const { result } = env.renderHook(() => env.useGameSession(config({ daily: true })))
    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))
    await env.act(() => result.current.startGame())

    await env.waitFor(() => expect(result.current.screen).toBe("finished"))
    expect(env.getDailyStatus).toHaveBeenCalledTimes(2)
  })

  it("does not get stuck on unknown when the fallback status check also fails", async () => {
    const env = await freshEnv()
    env.getDailyStatus.mockResolvedValueOnce(dailyStatus([modeStatus()]))
    env.createDailyGame.mockRejectedValue(conflictError())
    env.getDailyStatus.mockRejectedValueOnce(new Error("offline"))

    const { result } = env.renderHook(() => env.useGameSession(config({ daily: true })))
    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))
    await env.act(() => result.current.startGame())

    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))
    expect(result.current.screen).toBe("idle")
  })

  it("treats a non-409 daily failure as a plain error", async () => {
    const env = await freshEnv()
    env.getDailyStatus.mockResolvedValue(dailyStatus([modeStatus()]))
    env.createDailyGame.mockRejectedValue(new Error("offline"))

    const { result } = env.renderHook(() => env.useGameSession(config({ daily: true })))
    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))
    await env.act(() => result.current.startGame())

    expect(result.current.screen).toBe("error")
  })
})

describe("backToIdle", () => {
  it("discards a start response that arrives after it", async () => {
    const env = await freshEnv()
    const slow = deferred<GameOut>()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockReturnValue(slow.promise)

    const { result } = env.renderHook(() => env.useGameSession(config()))
    let starting!: Promise<void>
    env.act(() => {
      starting = result.current.startGame()
    })
    env.act(() => result.current.backToIdle())

    slow.resolve(gameOut())
    await env.act(async () => {
      await starting
    })

    expect(result.current.screen).toBe("idle")
  })

  it("re-checks the daily status on the way back", async () => {
    const env = await freshEnv()
    env.getDailyStatus.mockResolvedValue(dailyStatus([modeStatus()]))
    env.createDailyGame.mockResolvedValue(gameOut())

    const { result } = env.renderHook(() => env.useGameSession(config({ daily: true })))
    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))
    await env.act(() => result.current.startGame())
    const before = env.getDailyStatus.mock.calls.length

    await env.act(async () => {
      result.current.backToIdle()
      await flush()
    })

    expect(env.getDailyStatus.mock.calls.length).toBeGreaterThan(before)
  })

  it("does not re-check the daily status for a normal game", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut())

    const { result } = env.renderHook(() => env.useGameSession(config()))
    await env.act(() => result.current.startGame())

    await env.act(async () => {
      result.current.backToIdle()
      await flush()
    })

    expect(env.getDailyStatus).not.toHaveBeenCalled()
  })
})

describe("markDailyFinished", () => {
  it("updates only its own mode and leaves the others alone", async () => {
    const env = await freshEnv()
    const other = modeStatus({ game_type: "geoguessr", mode: "arcade", status: "not_played" })
    env.getDailyStatus.mockResolvedValue(dailyStatus([modeStatus(), other]))
    // Marking this mode finished feeds straight back into the idle effect (the screen is still
    // idle here), which then legitimately goes and loads the finished game - so getGame has to be
    // answerable, or that effect throws asynchronously into whichever test happens to be running.
    env.getGame.mockResolvedValue(gameOut({ id: "g5", finished: true, score: 77 }))

    const { result } = env.renderHook(() => env.useGameSession(config({ daily: true })))
    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))

    env.act(() => result.current.markDailyFinished("g5", 77))

    const cached = env.queryCache.peekCached<DailyStatusOut>(env.DAILY_STATUS_KEY)!
    expect(cached.modes).toEqual([
      expect.objectContaining({ mode: MODE, status: "finished", game_id: "g5", score: 77 }),
      other,
    ])
  })

  it("does nothing when the status was never loaded", async () => {
    // Never fabricate a DailyStatusOut: the other modes are unknown here, and the next real
    // revalidation fills them in correctly.
    const env = await freshEnv()
    const pending = deferred<DailyStatusOut>()
    env.getDailyStatus.mockReturnValue(pending.promise)

    const { result } = env.renderHook(() => env.useGameSession(config({ daily: true })))
    env.act(() => result.current.markDailyFinished("g5", 77))

    expect(env.queryCache.peekCached(env.DAILY_STATUS_KEY)).toBeUndefined()
    pending.resolve(dailyStatus([modeStatus()]))
  })

  it("does nothing for a normal game", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)

    const { result } = env.renderHook(() => env.useGameSession(config()))
    env.act(() => result.current.markDailyFinished("g5", 77))

    expect(env.queryCache.peekCached(env.DAILY_STATUS_KEY)).toBeUndefined()
  })
})

describe("the finished-daily notice", () => {
  // The wrapper is what menu/DailyGameRoute.tsx provides in the real app - the only consumer of
  // this signal, and what opens the "what now?" modal off it.
  function withNotifier(env: Awaited<ReturnType<typeof freshEnv>>, onFinished: () => void) {
    return ({ children }: { children: ReactNode }) =>
      env.react.createElement(env.DailyFinishedContext.Provider, { value: onFinished }, children)
  }

  it("fires once, when the finished screen appears and not before", async () => {
    const env = await freshEnv()
    env.getDailyStatus.mockResolvedValue(dailyStatus([modeStatus()]))
    env.createDailyGame.mockResolvedValue(gameOut())
    const onFinished = vi.fn()

    const { result, rerender } = env.renderHook(() => env.useGameSession(config({ daily: true })), {
      wrapper: withNotifier(env, onFinished),
    })
    await env.waitFor(() => expect(result.current.hasCurrentGame).toBe(false))
    await env.act(() => result.current.startGame())

    // useRoundGame marks the daily finished during its reveal hold, a beat before it switches
    // screens - nothing may be announced yet at that point.
    env.act(() => result.current.markDailyFinished("g1", 77))
    expect(onFinished).not.toHaveBeenCalled()

    env.act(() => result.current.setScreen("finished"))
    expect(onFinished).toHaveBeenCalledTimes(1)

    env.act(() => rerender())
    expect(onFinished).toHaveBeenCalledTimes(1)
  })

  it("stays quiet when an already-finished daily is re-opened", async () => {
    const env = await freshEnv()
    env.getDailyStatus.mockResolvedValue(
      dailyStatus([modeStatus({ status: "finished", game_id: "g9", score: 12 })]),
    )
    env.getGame.mockResolvedValue(gameOut({ id: "g9", finished: true, score: 12 }))
    const onFinished = vi.fn()

    const { result } = env.renderHook(() => env.useGameSession(config({ daily: true })), {
      wrapper: withNotifier(env, onFinished),
    })

    await env.waitFor(() => expect(result.current.screen).toBe("finished"))
    expect(onFinished).not.toHaveBeenCalled()
  })

  it("does nothing for a normal game finishing", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    const onFinished = vi.fn()

    const { result } = env.renderHook(() => env.useGameSession(config()), {
      wrapper: withNotifier(env, onFinished),
    })
    env.act(() => result.current.markDailyFinished("g5", 77))
    env.act(() => result.current.setScreen("finished"))

    expect(onFinished).not.toHaveBeenCalled()
  })
})

describe("markRecordBeaten", () => {
  const RECORDS_KEY = "game-records"

  it("writes a score that beats the cached best", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.queryCache.setCached(RECORDS_KEY, {
      records: [{ game_type: GAME_TYPE, mode: MODE, best_score: 10 }],
    })

    const { result } = env.renderHook(() => env.useGameSession(config()))
    env.act(() => result.current.markRecordBeaten(20))

    expect(env.queryCache.peekCached(RECORDS_KEY)).toEqual({
      records: [{ game_type: GAME_TYPE, mode: MODE, best_score: 20 }],
    })
  })

  it("leaves an equal or better cached best untouched", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    const cached = { records: [{ game_type: GAME_TYPE, mode: MODE, best_score: 30 }] }
    env.queryCache.setCached(RECORDS_KEY, cached)

    const { result } = env.renderHook(() => env.useGameSession(config()))
    env.act(() => result.current.markRecordBeaten(30))
    env.act(() => result.current.markRecordBeaten(29))

    expect(env.queryCache.peekCached(RECORDS_KEY)).toBe(cached)
  })

  it("adds an entry for a mode that had no record yet", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.queryCache.setCached(RECORDS_KEY, {
      records: [{ game_type: "geoguessr", mode: "arcade", best_score: 5 }],
    })

    const { result } = env.renderHook(() => env.useGameSession(config()))
    env.act(() => result.current.markRecordBeaten(20))

    expect(env.queryCache.peekCached(RECORDS_KEY)).toEqual({
      records: [
        { game_type: "geoguessr", mode: "arcade", best_score: 5 },
        { game_type: GAME_TYPE, mode: MODE, best_score: 20 },
      ],
    })
  })

  it("does nothing when the records were never loaded in this tab", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)

    const { result } = env.renderHook(() => env.useGameSession(config()))
    env.act(() => result.current.markRecordBeaten(20))

    expect(env.queryCache.peekCached(RECORDS_KEY)).toBeUndefined()
  })

  it("does nothing for a daily game, whose scores are not comparable to normal play", async () => {
    const env = await freshEnv()
    env.getDailyStatus.mockResolvedValue(dailyStatus([modeStatus()]))
    const cached = { records: [{ game_type: GAME_TYPE, mode: MODE, best_score: 10 }] }
    env.queryCache.setCached(RECORDS_KEY, cached)

    const { result } = env.renderHook(() => env.useGameSession(config({ daily: true })))
    env.act(() => result.current.markRecordBeaten(999))

    expect(env.queryCache.peekCached(RECORDS_KEY)).toBe(cached)
  })
})
