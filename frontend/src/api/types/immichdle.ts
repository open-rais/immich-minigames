// Immichdle's request/response DTOs - mirrors backend/src/api/dto/immichdle.py.

import type { GameType } from "./common"

export type AgeComparison = "older" | "younger" | "same" | "unknown"
export type CountComparison = "more" | "less" | "equal"
export type DateComparison = "before" | "after" | "same" | "unknown"

export interface ImmichdleCluesOut {
  age: AgeComparison
  asset_count: CountComparison
  first_appearance: DateComparison
  common_names: number
  ml_similarity: number | null
  assets_together: number
  // Magnitude buckets (< 1 year vs >= 1 year off), not exact diffs - see backend/src/games/
  // immichdle.py's ImmichdleClues docstring for why the exact gap is never exposed. null whenever
  // the underlying comparison has no meaningful magnitude ("same"/"equal"/"unknown").
  age_close: boolean | null
  first_appearance_close: boolean | null
  asset_count_close: boolean | null
  // Only meaningful when age/first_appearance is "unknown" - disambiguates "neither person has a
  // date" (green) from "only the target's is missing" (amber, since the guess's own date, when
  // known, is already visible via guess_birth_date/guess_first_asset_date below).
  age_both_unknown: boolean
  first_appearance_both_unknown: boolean
}

export interface ImmichdleRoundOut {
  game_type: typeof GameType.Immichdle
  id: string
  round_index: number
  // Redacted (null) until this round has been answered. The target itself is never in a round's
  // output at all - see GameOut.target_person_id/name.
  guess_person_id: string | null
  guess_person_name: string | null
  guess_asset_count: number | null
  guess_birth_date: string | null
  guess_first_asset_date: string | null
  correct: boolean | null
  clues: ImmichdleCluesOut | null
}

export interface ImmichdlePlayRoundIn {
  person_id: string
}
