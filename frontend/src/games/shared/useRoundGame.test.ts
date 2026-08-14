// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { GameType } from "../../api/types/common"
import type { GameOut, PlayRoundOut, RoundOut } from "../../api/types/common"
import type { TimelineRoundOut } from "../../api/types/timeline"

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

const GAME_TYPE = GameType.Timeline
const MODE = "arcade"
const REVEAL_HOLD_MS = 1500

// Timeline stands in for the whole "fixed rounds, one picker, auto-advance after a reveal hold"
// family this hook serves - the round type only matters here through isRound.
const isRound = (round: RoundOut): round is TimelineRoundOut =>
  round.game_type === GameType.Timeline

async function freshEnv() {
  vi.resetModules()
  const daily = await import("../../api/daily")
  const games = await import("../../api/games")
  const queryCache = await import("../../api/queryCache")
  const { useRoundGame } = await import("./useRoundGame")
  const rtl = await import("@testing-library/react")
  return {
    getDailyStatus: vi.mocked(daily.getDailyStatus),
    createDailyGame: vi.mocked(daily.createDailyGame),
    getCurrentGame: vi.mocked(games.getCurrentGame),
    createGame: vi.mocked(games.createGame),
    getGame: vi.mocked(games.getGame),
    queryCache,
    useRoundGame,
    ...rtl,
  }
}

function round(id: string, overrides: Partial<TimelineRoundOut> = {}): TimelineRoundOut {
  return {
    game_type: GameType.Timeline,
    id,
    round_index: 0,
    board: [],
    card_asset_id: `asset-${id}`,
    guess_slot: null,
    card_date: null,
    correct_slot: null,
    correct: null,
    score_delta: null,
    ...overrides,
  }
}

function gameOut(rounds: RoundOut[], overrides: Partial<GameOut> = {}): GameOut {
  return {
    id: "g1",
    type: GAME_TYPE,
    mode: MODE,
    score: 0,
    finished: false,
    rounds,
    ...overrides,
  }
}

function playResult(overrides: Partial<PlayRoundOut> = {}): PlayRoundOut {
  return {
    correct: true,
    score_delta: 1,
    score: 1,
    finished: false,
    answered_round: round("r1", { correct: true, score_delta: 1 }),
    next_round: round("r2"),
    ...overrides,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function config(overrides: Record<string, unknown> = {}) {
  return {
    gameType: GAME_TYPE,
    mode: MODE,
    revealHoldMs: REVEAL_HOLD_MS,
    isRound,
    playRound: vi.fn().mockResolvedValue(playResult()),
    onNewRound: vi.fn(),
    ...overrides,
  }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

// Fake timers are on for the reveal hold, so pending promises are drained by hand instead of with
// waitFor (which would try to schedule its own real timers).
async function settle(act: (fn: () => Promise<void>) => Promise<void>) {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

describe("applyGame", () => {
  it("takes the last round of the game as the pending one", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1"), round("r2"), round("r3")]))

    const { result } = env.renderHook(() => env.useRoundGame(config()))
    await env.act(() => result.current.startGame())

    expect(result.current.round?.id).toBe("r3")
    expect(result.current.phase).toBe("guessing")
    expect(result.current.screen).toBe("playing")
  })

  it("captures the score and the configured totals off the fetched game", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(
      gameOut([round("r1")], { score: 3, total_rounds: 5, total_people: null }),
    )

    const { result } = env.renderHook(() => env.useRoundGame(config()))
    await env.act(() => result.current.startGame())

    expect(result.current.game).toMatchObject({ id: "g1", score: 3, totalRounds: 5 })
  })

  it("shows the error screen when the round is not this game's own type", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(
      gameOut([{ game_type: GameType.Geoguessr, id: "r1" } as unknown as RoundOut]),
    )

    const { result } = env.renderHook(() => env.useRoundGame(config()))
    await env.act(() => result.current.startGame())

    expect(result.current.screen).toBe("error")
  })
})

describe("onResume / onNewRound", () => {
  it("fires onResume only when picking an existing game back up", async () => {
    const env = await freshEnv()
    const onResume = vi.fn()
    env.getCurrentGame.mockResolvedValue(gameOut([round("r1")]))
    env.createGame.mockResolvedValue(gameOut([round("r1")]))

    const { result } = env.renderHook(() => env.useRoundGame(config({ onResume })))
    await env.act(() => result.current.startGame())
    expect(onResume).not.toHaveBeenCalled()

    await env.act(() => result.current.resumeGame())
    expect(onResume).toHaveBeenCalledTimes(1)
    expect(onResume).toHaveBeenCalledWith(expect.objectContaining({ id: "g1" }))
  })

  it("fires onNewRound at game start and again on every auto-advance", async () => {
    const env = await freshEnv()
    const cfg = config()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1")]))

    const { result } = env.renderHook(() => env.useRoundGame(cfg))
    await env.act(() => result.current.startGame())
    expect(cfg.onNewRound).toHaveBeenCalledTimes(1)

    await env.act(() => result.current.submitGuess({ slot: 0 }))
    env.act(() => vi.advanceTimersByTime(REVEAL_HOLD_MS))

    expect(cfg.onNewRound).toHaveBeenCalledTimes(2)
  })
})

describe("submitGuess", () => {
  it("reveals the answered round and updates the score", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1")]))
    const cfg = config({
      playRound: vi.fn().mockResolvedValue(playResult({ score: 7, finished: false })),
    })

    const { result } = env.renderHook(() => env.useRoundGame(cfg))
    await env.act(() => result.current.startGame())
    await env.act(() => result.current.submitGuess({ slot: 1 }))

    expect(cfg.playRound).toHaveBeenCalledWith("g1", "r1", { slot: 1 })
    expect(result.current.phase).toBe("revealed")
    expect(result.current.revealed).toBe(true)
    expect(result.current.game).toMatchObject({ score: 7, finished: false })
    expect(result.current.round).toMatchObject({ id: "r1", correct: true })
  })

  it("ignores a second guess once the round is revealed", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1")]))
    const cfg = config()

    const { result } = env.renderHook(() => env.useRoundGame(cfg))
    await env.act(() => result.current.startGame())
    await env.act(() => result.current.submitGuess({ slot: 0 }))
    await env.act(() => result.current.submitGuess({ slot: 0 }))

    expect(cfg.playRound).toHaveBeenCalledTimes(1)
  })

  it("does nothing before a game has started", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    const cfg = config()

    const { result } = env.renderHook(() => env.useRoundGame(cfg))
    await env.act(() => result.current.submitGuess({ slot: 0 }))

    expect(cfg.playRound).not.toHaveBeenCalled()
  })

  it("shows the error screen when the answer comes back as another game's round", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1")]))
    const cfg = config({
      playRound: vi.fn().mockResolvedValue(
        playResult({
          answered_round: { game_type: GameType.Geoguessr, id: "r1" } as unknown as RoundOut,
        }),
      ),
    })

    const { result } = env.renderHook(() => env.useRoundGame(cfg))
    await env.act(() => result.current.startGame())
    await env.act(() => result.current.submitGuess({ slot: 0 }))

    expect(result.current.screen).toBe("error")
  })

  it("shows the error screen when the next round is another game's", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1")]))
    const cfg = config({
      playRound: vi.fn().mockResolvedValue(
        playResult({
          next_round: { game_type: GameType.Geoguessr, id: "r2" } as unknown as RoundOut,
        }),
      ),
    })

    const { result } = env.renderHook(() => env.useRoundGame(cfg))
    await env.act(() => result.current.startGame())
    await env.act(() => result.current.submitGuess({ slot: 0 }))

    expect(result.current.screen).toBe("error")
  })

  it("shows the error screen when the guess request fails", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1")]))
    const cfg = config({ playRound: vi.fn().mockRejectedValue(new Error("offline")) })

    const { result } = env.renderHook(() => env.useRoundGame(cfg))
    await env.act(() => result.current.startGame())
    await env.act(() => result.current.submitGuess({ slot: 0 }))

    expect(result.current.screen).toBe("error")
    expect(result.current.busy).toBe(false)
  })

  it("ignores a guess response that lands after the player backed out", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1")]))
    const slow = deferred<PlayRoundOut>()
    const cfg = config({ playRound: vi.fn().mockReturnValue(slow.promise) })

    const { result } = env.renderHook(() => env.useRoundGame(cfg))
    await env.act(() => result.current.startGame())

    let guessing!: Promise<void>
    env.act(() => {
      guessing = result.current.submitGuess({ slot: 0 })
    })
    env.act(() => result.current.backToIdle())
    slow.resolve(playResult())
    await env.act(async () => {
      await guessing
    })

    expect(result.current.screen).toBe("idle")
    expect(result.current.phase).not.toBe("revealed")
  })
})

describe("the reveal hold", () => {
  it("advances to the next round once the hold elapses", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1")]))

    const { result } = env.renderHook(() => env.useRoundGame(config()))
    await env.act(() => result.current.startGame())
    await env.act(() => result.current.submitGuess({ slot: 0 }))

    env.act(() => vi.advanceTimersByTime(REVEAL_HOLD_MS - 1))
    expect(result.current.phase).toBe("revealed")

    env.act(() => vi.advanceTimersByTime(1))
    expect(result.current.round?.id).toBe("r2")
    expect(result.current.phase).toBe("guessing")
  })

  it("goes to the finished screen when there is no next round", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1")]))
    const cfg = config({
      playRound: vi.fn().mockResolvedValue(playResult({ finished: true, next_round: null })),
    })

    const { result } = env.renderHook(() => env.useRoundGame(cfg))
    await env.act(() => result.current.startGame())
    await env.act(() => result.current.submitGuess({ slot: 0 }))
    env.act(() => vi.advanceTimersByTime(REVEAL_HOLD_MS))

    expect(result.current.screen).toBe("finished")
  })

  it("goes to the finished screen when the game is over even if a next round came back", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1")]))
    const cfg = config({
      playRound: vi.fn().mockResolvedValue(playResult({ finished: true, next_round: round("r2") })),
    })

    const { result } = env.renderHook(() => env.useRoundGame(cfg))
    await env.act(() => result.current.startGame())
    await env.act(() => result.current.submitGuess({ slot: 0 }))
    env.act(() => vi.advanceTimersByTime(REVEAL_HOLD_MS))

    expect(result.current.screen).toBe("finished")
  })

  it("clears the timer when the component unmounts mid-reveal", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1")]))

    const { result, unmount } = env.renderHook(() => env.useRoundGame(config()))
    await env.act(() => result.current.startGame())
    await env.act(() => result.current.submitGuess({ slot: 0 }))

    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe("finishing a game", () => {
  it("pushes the new personal best into the records cache", async () => {
    const env = await freshEnv()
    env.getCurrentGame.mockResolvedValue(null)
    env.createGame.mockResolvedValue(gameOut([round("r1")]))
    env.queryCache.setCached("game-records", {
      records: [{ game_type: GAME_TYPE, mode: MODE, best_score: 2 }],
    })
    const cfg = config({
      playRound: vi.fn().mockResolvedValue(playResult({ finished: true, score: 9 })),
    })

    const { result } = env.renderHook(() => env.useRoundGame(cfg))
    await env.act(() => result.current.startGame())
    await env.act(() => result.current.submitGuess({ slot: 0 }))

    expect(env.queryCache.peekCached("game-records")).toEqual({
      records: [{ game_type: GAME_TYPE, mode: MODE, best_score: 9 }],
    })
  })

  it("pushes a finished daily into the daily-status cache", async () => {
    const env = await freshEnv()
    env.getDailyStatus.mockResolvedValue({
      resets_at: "",
      server_now: "",
      modes: [
        { game_type: GAME_TYPE, mode: MODE, status: "not_played", game_id: null, score: null },
      ],
    })
    env.createDailyGame.mockResolvedValue(gameOut([round("r1")]))
    const cfg = config({
      daily: true,
      playRound: vi.fn().mockResolvedValue(playResult({ finished: true, score: 9 })),
    })

    const { result } = env.renderHook(() => env.useRoundGame(cfg))
    await settle(env.act)
    await env.act(() => result.current.startGame())
    await env.act(() => result.current.submitGuess({ slot: 0 }))

    expect(env.queryCache.peekCached<{ modes: unknown[] }>("daily-status")!.modes).toEqual([
      expect.objectContaining({ status: "finished", game_id: "g1", score: 9 }),
    ])
  })
})
