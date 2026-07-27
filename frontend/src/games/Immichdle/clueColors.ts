import type { ImmichdleRoundOut } from "../../api/types"

// Three-tier color scheme (green/amber/red), same intent everywhere: "match" is as-good-as-correct,
// "close" is a meaningful hint, "miss" is far off. Kept here as pure functions (no i18n/rendering)
// so the rules are easy to eyeball/tweak independently of ClueCell's markup.
export type ClueVariant = "match" | "close" | "miss"

export interface ClueResult {
  variant: ClueVariant
  // What renders as the big translucent glyph filling the tile's background (smashdle's look) -
  // null when the tile has no such watermark (e.g. a plain count).
  background: "up" | "down" | "question" | null
  kind: "date" | "count" | "percent" | "text"
  value?: string | number
}

// "up" means "guess someone with a higher value than this one" (older age / later first-appearance
// date / more assets), "down" means the opposite - mirrors MoreOrLess's more/fewer arrow convention.

function dateClue(
  comparison: "older" | "younger" | "same" | "unknown" | "before" | "after",
  close: boolean | null,
  bothUnknown: boolean,
  guessDate: string | null,
): ClueResult {
  if (comparison === "unknown") {
    if (bothUnknown) {
      // Neither person has a date - no direction to hint at, so no watermark either, just a plain "?".
      return { variant: "match", background: null, kind: "text", value: "?" }
    }
    if (guessDate === null) {
      // The guess itself has no date (the target's status is what's actually unknown to the
      // player) - nothing to show up front either, so both the glyph and the text are "?".
      return { variant: "close", background: "question", kind: "text", value: "?" }
    }
    // The guess has a date but the target doesn't - show the guess's own date up front, with a "?"
    // watermark standing in for the direction we can't determine.
    return { variant: "close", background: "question", kind: "date", value: guessDate }
  }
  if (comparison === "same") {
    return { variant: "match", background: null, kind: "date", value: guessDate ?? undefined }
  }
  const direction = comparison === "younger" || comparison === "before" ? "up" : "down"
  return { variant: close ? "close" : "miss", background: direction, kind: "date", value: guessDate ?? undefined }
}

export function ageClue(round: ImmichdleRoundOut): ClueResult {
  const clues = round.clues!
  return dateClue(clues.age, clues.age_close, clues.age_both_unknown, round.guess_birth_date)
}

export function firstAppearanceClue(round: ImmichdleRoundOut): ClueResult {
  const clues = round.clues!
  return dateClue(
    clues.first_appearance,
    clues.first_appearance_close,
    clues.first_appearance_both_unknown,
    round.guess_first_asset_date,
  )
}

export function assetCountClue(round: ImmichdleRoundOut): ClueResult {
  const clues = round.clues!
  if (clues.asset_count === "equal") {
    return { variant: "match", background: null, kind: "count", value: round.guess_asset_count ?? undefined }
  }
  const direction = clues.asset_count === "less" ? "up" : "down"
  const variant: ClueVariant = clues.asset_count_close ? "close" : "miss"
  return { variant, background: direction, kind: "count", value: round.guess_asset_count ?? undefined }
}

export function commonNamesClue(round: ImmichdleRoundOut): ClueResult {
  const clues = round.clues!
  const guessWordCount = (round.guess_person_name ?? "").trim().split(/\s+/).filter(Boolean).length
  const variant: ClueVariant = clues.common_names === 0 ? "miss" : clues.common_names === guessWordCount ? "match" : "close"
  return { variant, background: null, kind: "count", value: clues.common_names }
}

export function mlSimilarityClue(round: ImmichdleRoundOut): ClueResult {
  const similarity = round.clues!.ml_similarity
  if (similarity === null) return { variant: "miss", background: null, kind: "text", value: "?" }
  const variant: ClueVariant = similarity === 1 ? "match" : similarity > 0.85 ? "close" : "miss"
  return { variant, background: null, kind: "percent", value: Math.round(similarity * 100) }
}

export function assetsTogetherClue(round: ImmichdleRoundOut): ClueResult {
  const clues = round.clues!
  const variant: ClueVariant = round.correct ? "match" : clues.assets_together === 0 ? "miss" : "close"
  return { variant, background: null, kind: "count", value: clues.assets_together }
}

// The target row (roadmap #10 rounds review, ROUNDS-VIEW.md §3 F/§4.6) - one xTargetClue per xClue
// above, all `variant: "match"` and no background glyph (there's no direction to hint at when
// showing the target's own value, not a comparison).
export interface TargetSnapshot {
  personId: string
  name: string
  assetCount: number
  birthDate: string | null
  firstAssetDate: string | null
}

export function ageTargetClue(target: TargetSnapshot): ClueResult {
  if (target.birthDate === null) return { variant: "match", background: null, kind: "text", value: "?" }
  return { variant: "match", background: null, kind: "date", value: target.birthDate }
}

export function assetCountTargetClue(target: TargetSnapshot): ClueResult {
  return { variant: "match", background: null, kind: "count", value: target.assetCount }
}

export function firstAppearanceTargetClue(target: TargetSnapshot): ClueResult {
  if (target.firstAssetDate === null) return { variant: "match", background: null, kind: "text", value: "?" }
  return { variant: "match", background: null, kind: "date", value: target.firstAssetDate }
}

export function commonNamesTargetClue(target: TargetSnapshot): ClueResult {
  // The max achievable in this column - every word of the target's own name matches itself.
  const wordCount = target.name.trim().split(/\s+/).filter(Boolean).length
  return { variant: "match", background: null, kind: "count", value: wordCount }
}

export function mlSimilarityTargetClue(): ClueResult {
  return { variant: "match", background: null, kind: "text", value: "=" }
}

export function assetsTogetherTargetClue(): ClueResult {
  return { variant: "match", background: null, kind: "text", value: "-" }
}
