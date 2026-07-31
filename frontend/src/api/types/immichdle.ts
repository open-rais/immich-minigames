// Immichdle's request/response DTOs - mirrors backend/src/api/dto/immichdle.py. Both modes carry
// a `mode` field (not just `game_type`) - api/types/common.ts's RoundOut union needs it to
// disambiguate the two Immichdle round shapes, which otherwise share the same game_type.

import type { GameType, Mode } from "./common"

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
  // immichdle/persondle.py's PersonClues docstring for why the exact gap is never exposed. null
  // whenever the underlying comparison has no meaningful magnitude ("same"/"equal"/"unknown").
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
  mode: typeof Mode.Person
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

export type DominantFaceComparison = "match" | "close" | "miss"

export interface AlbumdleCluesOut {
  first_asset_date: DateComparison
  first_asset_date_close: boolean | null
  first_asset_date_both_unknown: boolean
  asset_count: CountComparison
  asset_count_close: boolean | null
  common_names: number
  similarity: number | null
  unique_face_count: CountComparison
  unique_face_count_close: boolean | null
  // The GUESS's own dominant face (not the target's - that stays secret until the game ends) -
  // rendered regardless of dominant_face_comparison, same as guess_birth_date is shown alongside
  // the age clue above.
  dominant_face_person_id: string | null
  dominant_face_name: string | null
  dominant_face_extra_count: number
  // null only when the GUESS has no named face at all - distinct from "has one, but it's absent
  // from the target" (miss).
  dominant_face_comparison: DominantFaceComparison | null
}

export interface AlbumdleRoundOut {
  game_type: typeof GameType.Immichdle
  mode: typeof Mode.Album
  id: string
  round_index: number
  // Redacted (null) until this round has been answered. The target itself is never in a round's
  // output at all - see GameOut.target_album_id/name.
  guess_album_id: string | null
  guess_album_name: string | null
  guess_asset_count: number | null
  guess_first_asset_date: string | null
  guess_unique_face_count: number | null
  correct: boolean | null
  clues: AlbumdleCluesOut | null
}

export interface AlbumdlePlayRoundIn {
  album_id: string
}
