import { describe, expect, it } from "vitest"
import { GameType, Mode } from "../../api/types/common"
import type {
  AlbumdleCluesOut,
  AlbumdleRoundOut,
  DateComparison,
  ImmichdleCluesOut,
  ImmichdleRoundOut,
} from "../../api/types/immichdle"
import {
  assetCountClue,
  commonNamesClue,
  firstAssetDateClue,
  similarityClue,
  uniqueFaceCountClue,
} from "./albumClueColors"
import { firstAppearanceClue } from "./clueColors"

const baseClues: AlbumdleCluesOut = {
  first_asset_date: "same",
  first_asset_date_close: null,
  first_asset_date_both_unknown: false,
  asset_count: "equal",
  asset_count_close: null,
  common_names: 0,
  similarity: 0,
  unique_face_count: "equal",
  unique_face_count_close: null,
  dominant_face_person_id: null,
  dominant_face_name: null,
  dominant_face_extra_count: 0,
  dominant_face_comparison: null,
}

function round(
  clues: Partial<AlbumdleCluesOut> = {},
  overrides: Partial<AlbumdleRoundOut> = {},
): AlbumdleRoundOut {
  return {
    game_type: GameType.Immichdle,
    mode: Mode.Album,
    id: "r1",
    round_index: 0,
    guess_album_id: "a1",
    guess_album_name: "Verano 2019",
    guess_asset_count: 40,
    guess_first_asset_date: "2019-06-21",
    guess_unique_face_count: 7,
    correct: false,
    clues: { ...baseClues, ...clues },
    ...overrides,
  }
}

describe("similarityClue", () => {
  it("floors a negative cosine to 0%", () => {
    expect(similarityClue(round({ similarity: -0.2 }))).toEqual({
      variant: "miss",
      background: null,
      kind: "percent",
      value: 0,
    })
  })

  it("puts the close/miss border strictly above 0.75, higher than the face-similarity one", () => {
    // CLIP album vectors read structurally higher than face embeddings, hence 0.75 here vs 0.3 in
    // clueColors.ts - if the two ever converge it should be a deliberate change, not a copy-paste.
    expect(similarityClue(round({ similarity: 0.76 })).variant).toBe("close")
    expect(similarityClue(round({ similarity: 0.75 })).variant).toBe("miss")
    expect(similarityClue(round({ similarity: 0.5 })).variant).toBe("miss")
  })

  it("treats an exact 1 as a match", () => {
    expect(similarityClue(round({ similarity: 1 })).variant).toBe("match")
  })

  it("shows a question mark when the similarity is unavailable", () => {
    expect(similarityClue(round({ similarity: null }))).toEqual({
      variant: "miss",
      background: null,
      kind: "text",
      value: "?",
    })
  })
})

describe("assetCountClue / uniqueFaceCountClue", () => {
  it("matches with no glyph when the counts are equal", () => {
    expect(assetCountClue(round({ asset_count: "equal" }))).toEqual({
      variant: "match",
      background: null,
      kind: "count",
      value: 40,
    })
    expect(uniqueFaceCountClue(round({ unique_face_count: "equal" }))).toEqual({
      variant: "match",
      background: null,
      kind: "count",
      value: 7,
    })
  })

  it("points up when the guess has fewer and down when it has more", () => {
    expect(assetCountClue(round({ asset_count: "less" })).background).toBe("up")
    expect(assetCountClue(round({ asset_count: "more" })).background).toBe("down")
    expect(uniqueFaceCountClue(round({ unique_face_count: "less" })).background).toBe("up")
    expect(uniqueFaceCountClue(round({ unique_face_count: "more" })).background).toBe("down")
  })

  it("uses each clue's own close flag", () => {
    expect(assetCountClue(round({ asset_count: "less", asset_count_close: true })).variant).toBe(
      "close",
    )
    expect(
      uniqueFaceCountClue(round({ unique_face_count: "more", unique_face_count_close: false }))
        .variant,
    ).toBe("miss")
  })
})

describe("commonNamesClue", () => {
  it("misses on zero, matches on every word of the album name, is close in between", () => {
    expect(commonNamesClue(round({ common_names: 0 })).variant).toBe("miss")
    expect(commonNamesClue(round({ common_names: 2 })).variant).toBe("match") // "Verano 2019"
    expect(commonNamesClue(round({ common_names: 1 })).variant).toBe("close")
  })

  it("counts words correctly despite padding and repeated whitespace", () => {
    expect(
      commonNamesClue(round({ common_names: 2 }, { guess_album_name: " Verano   2019 " })).variant,
    ).toBe("match")
  })
})

describe("date clue parity with clueColors.ts", () => {
  // The two dateClue implementations are duplicated on purpose (this project's no-cross-dedup
  // policy - see CLAUDE.md), which means nothing but this test would notice them drifting apart.
  // The person-side version also accepts "older"/"younger"; the shared subset is what's compared.
  const comparisons: DateComparison[] = ["before", "after", "same", "unknown"]

  function personRound(
    comparison: DateComparison,
    close: boolean | null,
    bothUnknown: boolean,
    guessDate: string | null,
  ): ImmichdleRoundOut {
    const clues: ImmichdleCluesOut = {
      age: "same",
      asset_count: "equal",
      first_appearance: comparison,
      common_names: 0,
      ml_similarity: null,
      assets_together: 0,
      age_close: null,
      first_appearance_close: close,
      asset_count_close: null,
      age_both_unknown: false,
      first_appearance_both_unknown: bothUnknown,
    }
    return {
      game_type: GameType.Immichdle,
      mode: Mode.Person,
      id: "r1",
      round_index: 0,
      guess_person_id: "p1",
      guess_person_name: "Ada",
      guess_asset_count: 0,
      guess_birth_date: null,
      guess_first_asset_date: guessDate,
      correct: false,
      clues,
    }
  }

  it("produces identical results for every equivalent input", () => {
    for (const comparison of comparisons) {
      for (const close of [true, false, null]) {
        for (const bothUnknown of [true, false]) {
          for (const guessDate of ["2019-06-21", null]) {
            const album = firstAssetDateClue(
              round(
                {
                  first_asset_date: comparison,
                  first_asset_date_close: close,
                  first_asset_date_both_unknown: bothUnknown,
                },
                { guess_first_asset_date: guessDate },
              ),
            )
            const person = firstAppearanceClue(
              personRound(comparison, close, bothUnknown, guessDate),
            )
            expect(album, `${comparison}/${close}/${bothUnknown}/${guessDate}`).toEqual(person)
          }
        }
      }
    }
  })
})
