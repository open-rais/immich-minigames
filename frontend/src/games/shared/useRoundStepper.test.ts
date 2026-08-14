// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { GameType } from "../../api/types/common"
import type { GameOut, RoundOut } from "../../api/types/common"
import type { TimelineRoundOut } from "../../api/types/timeline"
import { useRoundStepper } from "./useRoundStepper"

const isRound = (round: RoundOut): round is TimelineRoundOut =>
  round.game_type === GameType.Timeline
const isAnswered = (round: TimelineRoundOut) => round.correct !== null

function round(id: string, answered: boolean): TimelineRoundOut {
  return {
    game_type: GameType.Timeline,
    id,
    round_index: 0,
    board: [],
    card_asset_id: "a",
    guess_slot: answered ? 0 : null,
    card_date: answered ? "2020-01-01" : null,
    correct_slot: answered ? 0 : null,
    correct: answered ? true : null,
    score_delta: answered ? 1 : null,
  }
}

const foreignRound = { game_type: GameType.Geoguessr, id: "x" } as unknown as RoundOut

function game(rounds: RoundOut[]): GameOut {
  return { id: "g1", type: GameType.Timeline, mode: "arcade", score: 0, finished: true, rounds }
}

describe("useRoundStepper", () => {
  it("drops rounds from other games and rounds still pending an answer", () => {
    const { result } = renderHook(() =>
      useRoundStepper(
        game([round("r1", true), foreignRound, round("r2", true), round("r3", false)]),
        isRound,
        isAnswered,
      ),
    )

    expect(result.current!.total).toBe(2)
    expect(result.current!.round.id).toBe("r1")
  })

  it("counts the filtered rounds, not the game's whole round list", () => {
    const { result } = renderHook(() =>
      useRoundStepper(game([round("r1", true), foreignRound, foreignRound]), isRound, isAnswered),
    )

    expect(result.current!.total).toBe(1)
  })

  it("returns nothing when no round survived the filters", () => {
    const { result } = renderHook(() =>
      useRoundStepper(game([round("r1", false), foreignRound]), isRound, isAnswered),
    )

    expect(result.current).toBeNull()
  })

  it("returns nothing for a game with no rounds at all", () => {
    const { result } = renderHook(() => useRoundStepper(game([]), isRound, isAnswered))
    expect(result.current).toBeNull()
  })

  it("steps forward and back through the answered rounds", () => {
    const { result } = renderHook(() =>
      useRoundStepper(game([round("r1", true), round("r2", true)]), isRound, isAnswered),
    )

    act(() => result.current!.next())
    expect(result.current!.index).toBe(1)
    expect(result.current!.round.id).toBe("r2")

    act(() => result.current!.prev())
    expect(result.current!.index).toBe(0)
    expect(result.current!.round.id).toBe("r1")
  })

  it("stays put at both ends instead of running off the list", () => {
    const { result } = renderHook(() =>
      useRoundStepper(game([round("r1", true), round("r2", true)]), isRound, isAnswered),
    )

    act(() => result.current!.prev())
    expect(result.current!.index).toBe(0)

    act(() => result.current!.next())
    act(() => result.current!.next())
    expect(result.current!.index).toBe(1)
    expect(result.current!.round.id).toBe("r2")
  })
})
