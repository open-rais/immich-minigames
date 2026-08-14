import type { TFunction } from "i18next"
import { describe, expect, it } from "vitest"
import { GameType } from "../../api/types/common"
import type { GameOut, RoundOut } from "../../api/types/common"
import type { DateguessrRoundOut } from "../../api/types/dateguessr"
import type { GeoguessrRoundOut } from "../../api/types/geoguessr"
import type { ImmichdleRoundOut } from "../../api/types/immichdle"
import type { HiddenFaceOut, WhosThatPersonRoundOut } from "../../api/types/whosThatPerson"
import {
  buildDailyShareAllMessage,
  buildDailyShareBody,
  buildDailyShareMessage,
  buildDailyShareOneLiner,
} from "./dailyShareText"

// A recording stand-in for i18next's t: the tests assert on the keys and the interpolated values,
// never on translated copy, so editing the i18n .json files can't break them.
function makeT() {
  const calls: { key: string; opts?: Record<string, unknown> }[] = []
  const t = ((key: string, opts?: Record<string, unknown>) => {
    calls.push({ key, opts })
    return opts === undefined ? key : `${key}:${JSON.stringify(opts)}`
  }) as unknown as TFunction
  const optsFor = (key: string) => calls.find((c) => c.key === key)?.opts
  const allOptsFor = (key: string) => calls.filter((c) => c.key === key).map((c) => c.opts)
  return { t, calls, optsFor, allOptsFor }
}

function game(type: string, rounds: RoundOut[] = [], overrides: Partial<GameOut> = {}): GameOut {
  return {
    id: "g1",
    type,
    mode: "whatever",
    score: 1234,
    finished: true,
    rounds,
    daily_challenge_date: "2026-08-13",
    ...overrides,
  }
}

function geoRound(scoreDelta: number | null, distanceKm: number | null): GeoguessrRoundOut {
  return {
    game_type: GameType.Geoguessr,
    id: "r",
    round_index: 0,
    asset_ids: ["a"],
    guess_latitude: 0,
    guess_longitude: 0,
    actual_latitude: 0,
    actual_longitude: 0,
    distance_km: distanceKm,
    score_delta: scoreDelta,
  }
}

function dateRound(scoreDelta: number | null, daysOff: number | null): DateguessrRoundOut {
  return {
    game_type: GameType.Dateguessr,
    id: "r",
    round_index: 0,
    asset_ids: ["a"],
    guess_date: "2020-01-01",
    actual_date: "2020-01-01",
    days_off: daysOff,
    score_delta: scoreDelta,
  }
}

function immichdleRound(correct: boolean | null): ImmichdleRoundOut {
  return {
    game_type: GameType.Immichdle,
    mode: "person",
    id: "r",
    round_index: 0,
    guess_person_id: "p",
    guess_person_name: "Ada",
    guess_asset_count: 0,
    guess_birth_date: null,
    guess_first_asset_date: null,
    correct,
    clues: null,
  } as ImmichdleRoundOut
}

function face(correct: boolean | null): HiddenFaceOut {
  return {
    face_id: "f",
    image_width: 100,
    image_height: 100,
    bounding_box_x1: 0,
    bounding_box_y1: 0,
    bounding_box_x2: 10,
    bounding_box_y2: 10,
    person_id: null,
    person_name: null,
    correct,
    guess_person_id: null,
    guess_person_name: null,
  }
}

function whosThatPersonRound(faces: HiddenFaceOut[]): WhosThatPersonRoundOut {
  return {
    game_type: GameType.WhosThatPerson,
    id: "r",
    round_index: 0,
    asset_id: "a",
    faces,
    correct: null,
    score_delta: 0,
  }
}

// One representative finished game per implemented game type, for the parametrized tests below.
const gamesByType: Record<GameType, GameOut> = {
  [GameType.MoreOrLess]: game(GameType.MoreOrLess),
  [GameType.Geoguessr]: game(GameType.Geoguessr, [geoRound(4000, 12.34), geoRound(1000, 900)]),
  [GameType.Dateguessr]: game(GameType.Dateguessr, [dateRound(4000, 3), dateRound(1000, 400)]),
  [GameType.Immichdle]: game(GameType.Immichdle, [immichdleRound(false), immichdleRound(true)]),
  [GameType.WhosThatPerson]: game(
    GameType.WhosThatPerson,
    [whosThatPersonRound([face(true), face(false)])],
    { total_people: 2 },
  ),
  [GameType.Timeline]: game(GameType.Timeline, [], { score: 7 }),
}

describe("buildDailyShareBody", () => {
  it("has a dedicated branch for every game type, not just the generic total", () => {
    // Parametrized over the enum on purpose: adding a seventh game without its own branch here
    // makes this fail instead of silently shipping a score-only share text.
    for (const type of Object.values(GameType)) {
      const { t } = makeT()
      const body = buildDailyShareBody(t, gamesByType[type])
      const { t: fallbackT } = makeT()
      const generic = buildDailyShareBody(fallbackT, game("some-unknown-game"))
      expect(body, `game type ${type}`).not.toBe(generic)
    }
  })

  it("falls back to the plain total for an unrecognized game type", () => {
    const { t, calls } = makeT()
    const body = buildDailyShareBody(t, game("some-unknown-game", [], { score: 55 }))
    expect(calls).toEqual([{ key: "daily.share.total", opts: { score: 55 } }])
    expect(body).toBe('daily.share.total:{"score":55}')
  })

  it("colors each round green/amber/red at the exact 0.8 and 0.4 thresholds", () => {
    const { t, allOptsFor } = makeT()
    buildDailyShareBody(
      t,
      game(GameType.Geoguessr, [
        geoRound(5000, 0), // 100%
        geoRound(4000, 0), // exactly 80%
        geoRound(3999, 0), // a hair under
        geoRound(2000, 0), // exactly 40%
        geoRound(1999, 0), // a hair under
        geoRound(0, 0),
      ]),
    )
    const colors = allOptsFor("daily.share.roundLine").map((o) => o!.color)
    expect(colors).toEqual(["🟩", "🟩", "🟨", "🟨", "🟥", "🟥"])
  })

  it("counts a null score_delta as zero points, never as NaN", () => {
    const { t, allOptsFor } = makeT()
    buildDailyShareBody(t, game(GameType.Geoguessr, [geoRound(null, 5)]))
    const line = allOptsFor("daily.share.roundLine")[0]!
    expect(line.points).toBe(0)
    expect(line.color).toBe("🟥")
  })

  it("shows a question mark for an unknown distance instead of null or undefined", () => {
    const { t, optsFor } = makeT()
    buildDailyShareBody(t, game(GameType.Geoguessr, [geoRound(1000, null)]))
    expect(optsFor("daily.share.km")).toEqual({ value: "?" })
  })

  it("shows one decimal for a known distance", () => {
    const { t, optsFor } = makeT()
    buildDailyShareBody(t, game(GameType.Geoguessr, [geoRound(1000, 12.36)]))
    expect(optsFor("daily.share.km")).toEqual({ value: "12.4" })
  })

  it("shows a question mark for unknown days off", () => {
    const { t, allOptsFor } = makeT()
    buildDailyShareBody(t, game(GameType.Dateguessr, [dateRound(1000, null), dateRound(1000, 3)]))
    expect(allOptsFor("daily.share.days")).toEqual([{ count: "?" }, { count: 3 }])
  })

  it("wins Immichdle only when the last round is the correct one", () => {
    const { t, optsFor } = makeT()
    buildDailyShareBody(t, game(GameType.Immichdle, [immichdleRound(false), immichdleRound(true)]))
    expect(optsFor("daily.share.immichdleWon")).toEqual({ attempts: 2 })
  })

  it("loses Immichdle when the last round is wrong, even if an earlier one was right", () => {
    const { t, calls } = makeT()
    buildDailyShareBody(t, game(GameType.Immichdle, [immichdleRound(true), immichdleRound(false)]))
    expect(calls.map((c) => c.key)).toContain("daily.share.immichdleLost")
  })

  it("survives an Immichdle game with no rounds at all", () => {
    const { t, calls } = makeT()
    expect(() => buildDailyShareBody(t, game(GameType.Immichdle, []))).not.toThrow()
    expect(calls.map((c) => c.key)).toContain("daily.share.immichdleLost")
  })

  it("takes the WhosThatPerson total from the game when it reports one", () => {
    const { t, optsFor } = makeT()
    buildDailyShareBody(
      t,
      game(GameType.WhosThatPerson, [whosThatPersonRound([face(true), face(false)])], {
        total_people: 9,
      }),
    )
    expect(optsFor("daily.share.whosThatPerson")).toEqual({ correct: 1, total: 9 })
  })

  it("falls back to counting faces when the game reports no total", () => {
    const { t, optsFor } = makeT()
    buildDailyShareBody(
      t,
      game(
        GameType.WhosThatPerson,
        [whosThatPersonRound([face(true), face(false)]), whosThatPersonRound([face(true)])],
        { total_people: null },
      ),
    )
    expect(optsFor("daily.share.whosThatPerson")).toEqual({ correct: 2, total: 3 })
  })

  it("uses the score as Timeline's card count", () => {
    const { t, optsFor } = makeT()
    buildDailyShareBody(t, game(GameType.Timeline, [], { score: 7 }))
    expect(optsFor("daily.share.timeline")).toEqual({ count: 7 })
  })
})

describe("buildDailyShareOneLiner", () => {
  it("stays on a single line for every game type - that is its whole reason to exist", () => {
    for (const type of Object.values(GameType)) {
      const { t } = makeT()
      expect(buildDailyShareOneLiner(t, gamesByType[type]), `game type ${type}`).not.toContain("\n")
    }
  })

  it("stays on a single line for an unrecognized game type too", () => {
    const { t } = makeT()
    expect(buildDailyShareOneLiner(t, game("some-unknown-game"))).toBe("1234pts")
  })

  it("condenses Geoguessr and Dateguessr to one square per round plus the score", () => {
    const { t } = makeT()
    const line = buildDailyShareOneLiner(
      t,
      game(GameType.Geoguessr, [geoRound(5000, 1), geoRound(0, 1)], { score: 5000 }),
    )
    expect(line).toBe("🟩🟥 5000pts")
  })
})

describe("buildDailyShareMessage", () => {
  it("opens with the header and closes with the link", () => {
    const { t } = makeT()
    const message = buildDailyShareMessage(
      t,
      game(GameType.MoreOrLess),
      "Más o menos",
      "Fotos por persona",
      "https://example.test/daily",
    )
    const lines = message.split("\n")
    expect(lines[0]).toContain("daily.share.header")
    expect(lines[lines.length - 1]).toBe("https://example.test/daily")
  })

  it("passes the game and mode titles and the challenge date to the header", () => {
    const { t, optsFor } = makeT()
    buildDailyShareMessage(t, gamesByType[GameType.MoreOrLess], "Geo", "Arcade", "link")
    expect(optsFor("daily.share.header")).toEqual({ game: "Geo - Arcade", date: "2026-08-13" })
  })

  it("uses an empty date rather than the word null for a non-daily game", () => {
    const { t, optsFor } = makeT()
    buildDailyShareMessage(
      t,
      game(GameType.MoreOrLess, [], { daily_challenge_date: null }),
      "Geo",
      "Arcade",
      "link",
    )
    expect(optsFor("daily.share.header")).toEqual({ game: "Geo - Arcade", date: "" })
  })
})

describe("buildDailyShareAllMessage", () => {
  it("survives an empty entry list without inventing a date", () => {
    const { t, optsFor } = makeT()
    const message = buildDailyShareAllMessage(t, [], "https://example.test/daily")
    expect(optsFor("daily.share.allHeader")).toEqual({ date: "" })
    expect(message.split("\n")).toEqual([
      'daily.share.allHeader:{"date":""}',
      "https://example.test/daily",
    ])
  })

  it("emits one line per entry between the header and the link", () => {
    const { t } = makeT()
    const message = buildDailyShareAllMessage(
      t,
      [
        { gameTitle: "Geo", modeTitle: "Arcade", game: gamesByType[GameType.Geoguessr] },
        { gameTitle: "Timeline", modeTitle: "Arcade", game: gamesByType[GameType.Timeline] },
      ],
      "https://example.test/daily",
    )
    const lines = message.split("\n")
    expect(lines).toHaveLength(4)
    expect(lines[1]).toContain("Geo - Arcade: ")
    expect(lines[2]).toContain("Timeline - Arcade: ")
  })

  it("takes the date from the first entry", () => {
    const { t, optsFor } = makeT()
    buildDailyShareAllMessage(
      t,
      [
        {
          gameTitle: "Geo",
          modeTitle: "Arcade",
          game: game(GameType.MoreOrLess, [], { daily_challenge_date: "2026-01-02" }),
        },
      ],
      "link",
    )
    expect(optsFor("daily.share.allHeader")).toEqual({ date: "2026-01-02" })
  })
})
