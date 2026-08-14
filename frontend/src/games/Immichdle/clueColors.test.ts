import { describe, expect, it } from "vitest"
import { GameType, Mode } from "../../api/types/common"
import type { ImmichdleCluesOut, ImmichdleRoundOut } from "../../api/types/immichdle"
import {
  ageClue,
  assetCountClue,
  assetsTogetherClue,
  commonNamesClue,
  commonNamesTargetClue,
  firstAppearanceClue,
  mlSimilarityClue,
} from "./clueColors"
import type { TargetSnapshot } from "./clueColors"

const baseClues: ImmichdleCluesOut = {
  age: "same",
  asset_count: "equal",
  first_appearance: "same",
  common_names: 0,
  ml_similarity: 0,
  assets_together: 0,
  age_close: null,
  first_appearance_close: null,
  asset_count_close: null,
  age_both_unknown: false,
  first_appearance_both_unknown: false,
}

function round(
  clues: Partial<ImmichdleCluesOut> = {},
  overrides: Partial<ImmichdleRoundOut> = {},
): ImmichdleRoundOut {
  return {
    game_type: GameType.Immichdle,
    mode: Mode.Person,
    id: "r1",
    round_index: 0,
    guess_person_id: "p1",
    guess_person_name: "Ada Lovelace",
    guess_asset_count: 12,
    guess_birth_date: "1815-12-10",
    guess_first_asset_date: "2019-04-01",
    correct: false,
    clues: { ...baseClues, ...clues },
    ...overrides,
  }
}

describe("mlSimilarityClue", () => {
  it("floors a negative cosine to 0% instead of showing a negative percentage", () => {
    const clue = mlSimilarityClue(round({ ml_similarity: -0.42 }))
    expect(clue).toEqual({ variant: "miss", background: null, kind: "percent", value: 0 })
  })

  it("treats an exact 1 as a match", () => {
    expect(mlSimilarityClue(round({ ml_similarity: 1 })).variant).toBe("match")
  })

  it("puts the close/miss border strictly above 0.3", () => {
    expect(mlSimilarityClue(round({ ml_similarity: 0.31 })).variant).toBe("close")
    expect(mlSimilarityClue(round({ ml_similarity: 0.3 })).variant).toBe("miss")
    expect(mlSimilarityClue(round({ ml_similarity: 0.301 })).variant).toBe("close")
  })

  it("rounds the displayed percentage", () => {
    expect(mlSimilarityClue(round({ ml_similarity: 0.876 })).value).toBe(88)
  })

  it("shows a question mark when the similarity is unavailable", () => {
    expect(mlSimilarityClue(round({ ml_similarity: null }))).toEqual({
      variant: "miss",
      background: null,
      kind: "text",
      value: "?",
    })
  })
})

describe("commonNamesClue", () => {
  it("misses on zero shared words", () => {
    expect(commonNamesClue(round({ common_names: 0 })).variant).toBe("miss")
  })

  it("matches when every word of the guess is shared", () => {
    const clue = commonNamesClue(round({ common_names: 2 }, { guess_person_name: "Ada Lovelace" }))
    expect(clue).toEqual({ variant: "match", background: null, kind: "count", value: 2 })
  })

  it("is close when only some words are shared", () => {
    const clue = commonNamesClue(
      round({ common_names: 1 }, { guess_person_name: "Ada Byron Lovelace" }),
    )
    expect(clue.variant).toBe("close")
  })

  it("counts words correctly despite padding and repeated whitespace", () => {
    const clue = commonNamesClue(
      round({ common_names: 2 }, { guess_person_name: "  Ada   Lovelace  " }),
    )
    expect(clue.variant).toBe("match") // 2 words, not 4 empty-string artifacts
  })

  it("does not blow up on a missing guess name", () => {
    expect(commonNamesClue(round({ common_names: 0 }, { guess_person_name: null })).variant).toBe(
      "miss",
    )
  })
})

describe("ageClue / firstAppearanceClue - the unknown quadrants", () => {
  it("matches with a plain ? when neither person has a date", () => {
    const clue = ageClue(round({ age: "unknown", age_both_unknown: true }))
    expect(clue).toEqual({ variant: "match", background: null, kind: "text", value: "?" })
  })

  it("shows a ? glyph and no date when only the guess lacks one", () => {
    const clue = ageClue(
      round({ age: "unknown", age_both_unknown: false }, { guess_birth_date: null }),
    )
    expect(clue).toEqual({ variant: "close", background: "question", kind: "text", value: "?" })
  })

  it("shows the guess's own date under a ? glyph when only the target lacks one", () => {
    const clue = ageClue(
      round({ age: "unknown", age_both_unknown: false }, { guess_birth_date: "1815-12-10" }),
    )
    expect(clue).toEqual({
      variant: "close",
      background: "question",
      kind: "date",
      value: "1815-12-10",
    })
  })

  it("matches with no glyph when both dates are the same", () => {
    const clue = ageClue(round({ age: "same" }))
    expect(clue).toEqual({
      variant: "match",
      background: null,
      kind: "date",
      value: "1815-12-10",
    })
  })
})

describe("ageClue / firstAppearanceClue - the arrow convention", () => {
  it("points up for younger and before (guess higher next)", () => {
    expect(ageClue(round({ age: "younger", age_close: false })).background).toBe("up")
    expect(
      firstAppearanceClue(round({ first_appearance: "before", first_appearance_close: false }))
        .background,
    ).toBe("up")
  })

  it("points down for older and after", () => {
    expect(ageClue(round({ age: "older", age_close: false })).background).toBe("down")
    expect(
      firstAppearanceClue(round({ first_appearance: "after", first_appearance_close: false }))
        .background,
    ).toBe("down")
  })

  it("uses the close flag for the variant, independently of the direction", () => {
    expect(ageClue(round({ age: "older", age_close: true })).variant).toBe("close")
    expect(ageClue(round({ age: "older", age_close: false })).variant).toBe("miss")
    expect(ageClue(round({ age: "younger", age_close: null })).variant).toBe("miss")
  })
})

describe("assetCountClue", () => {
  it("matches with no glyph when the counts are equal", () => {
    expect(assetCountClue(round({ asset_count: "equal" }))).toEqual({
      variant: "match",
      background: null,
      kind: "count",
      value: 12,
    })
  })

  it("points up when the guess has fewer assets than the target", () => {
    expect(assetCountClue(round({ asset_count: "less" })).background).toBe("up")
  })

  it("points down when the guess has more", () => {
    expect(assetCountClue(round({ asset_count: "more" })).background).toBe("down")
  })
})

describe("assetsTogetherClue", () => {
  it("matches a correct guess even when the pair share no photos", () => {
    const clue = assetsTogetherClue(round({ assets_together: 0 }, { correct: true }))
    expect(clue.variant).toBe("match")
  })

  it("misses when they share no photos and the guess is wrong", () => {
    expect(assetsTogetherClue(round({ assets_together: 0 }, { correct: false })).variant).toBe(
      "miss",
    )
  })

  it("is close when they appear together at least once", () => {
    expect(assetsTogetherClue(round({ assets_together: 1 }, { correct: false })).variant).toBe(
      "close",
    )
  })
})

describe("commonNamesTargetClue", () => {
  const target: TargetSnapshot = {
    personId: "t1",
    name: "  Grace   Brewster Hopper ",
    assetCount: 0,
    birthDate: null,
    firstAssetDate: null,
  }

  it("reports the target's own word count, which is the column's ceiling", () => {
    expect(commonNamesTargetClue(target)).toEqual({
      variant: "match",
      background: null,
      kind: "count",
      value: 3,
    })
  })
})
