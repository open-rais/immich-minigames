import { describe, expect, it } from "vitest"
import { GameType } from "../../api/types/common"
import type { RoundOut } from "../../api/types/common"
import type { TimelineCardOut } from "../../api/types/timeline"
import { adjustedMarkerSlot, insertCard, isTimelineRound, toTrackCard } from "./timelineBoard"

const card = (id: string, date: string): TimelineCardOut => ({ asset_id: id, date })

const board: TimelineCardOut[] = [card("a", "2001-01-01"), card("b", "2010-01-01")]

describe("insertCard", () => {
  it("inserts at the front", () => {
    expect(insertCard(board, 0, card("new", "1990-01-01")).map((c) => c.asset_id)).toEqual([
      "new",
      "a",
      "b",
    ])
  })

  it("inserts in the middle", () => {
    expect(insertCard(board, 1, card("new", "2005-01-01")).map((c) => c.asset_id)).toEqual([
      "a",
      "new",
      "b",
    ])
  })

  it("inserts past the last card when the slot equals the board length", () => {
    expect(
      insertCard(board, board.length, card("new", "2020-01-01")).map((c) => c.asset_id),
    ).toEqual(["a", "b", "new"])
  })

  it("inserts into an empty board", () => {
    expect(insertCard([], 0, card("new", "2020-01-01"))).toEqual([card("new", "2020-01-01")])
  })

  it("leaves the original board untouched", () => {
    const original = [...board]
    insertCard(board, 1, card("new", "2005-01-01"))
    expect(board).toEqual(original)
  })
})

describe("adjustedMarkerSlot", () => {
  it("leaves a correct slot before the guess where it is", () => {
    expect(adjustedMarkerSlot(0, 2)).toBe(0)
    expect(adjustedMarkerSlot(1, 2)).toBe(1)
  })

  it("shifts a correct slot after the guess right by one, to make room for the guessed card", () => {
    expect(adjustedMarkerSlot(3, 2)).toBe(4)
    expect(adjustedMarkerSlot(2, 0)).toBe(3)
  })
})

describe("isTimelineRound", () => {
  it("accepts a timeline round", () => {
    const round = { game_type: GameType.Timeline, id: "r1" } as unknown as RoundOut
    expect(isTimelineRound(round)).toBe(true)
  })

  it("rejects a round from another game", () => {
    const round = { game_type: GameType.MoreOrLess, id: "r1" } as unknown as RoundOut
    expect(isTimelineRound(round)).toBe(false)
  })
})

describe("toTrackCard", () => {
  it("renames the wire field to the track's own", () => {
    expect(toTrackCard(card("asset-1", "2001-01-01"))).toEqual({
      assetId: "asset-1",
      date: "2001-01-01",
    })
  })
})
