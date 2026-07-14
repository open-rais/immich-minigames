// Mirrors backend/src/api/schemas.py - keep field names in sync with that file.

// Canonical game_type / mode identifiers, mirroring the keys of
// backend/src/services/games_service.py's _GAME_CLASSES / _ROUND_CLASSES. Single source so the
// catalog, the game components and the discriminated-union tags below don't each hardcode the same
// strings.
export const GameType = {
  MoreOrLess: "more-or-less",
  Geoguessr: "geoguessr",
  Dateguessr: "dateguessr",
  Immichdle: "immichdle",
} as const
export type GameType = (typeof GameType)[keyof typeof GameType]

export const Mode = {
  PersonAssets: "personAssets",
  DistanceBetweenGuess: "distanceBetweenGuess",
  DaysToDate: "daysToDate",
  Person: "person",
} as const
export type Mode = (typeof Mode)[keyof typeof Mode]

export type MoreOrLessGuess = "more" | "less"

export interface CreateGameIn {
  type: string
  mode: string
}

export interface MoreOrLessRoundOut {
  game_type: typeof GameType.MoreOrLess
  id: string
  round_index: number
  reference_id: string
  reference_name: string
  reference_asset_count: number
  candidate_id: string
  candidate_name: string
  // Redacted (null) until this round has been answered.
  candidate_asset_count: number | null
  guess: MoreOrLessGuess | null
  correct: boolean | null
}

export interface GeoguessrRoundOut {
  game_type: typeof GameType.Geoguessr
  id: string
  round_index: number
  asset_id: string
  guess_latitude: number | null
  guess_longitude: number | null
  // Redacted (null) until this round has been answered.
  actual_latitude: number | null
  actual_longitude: number | null
  distance_km: number | null
  score_delta: number | null
}

export interface DateguessrRoundOut {
  game_type: typeof GameType.Dateguessr
  id: string
  round_index: number
  asset_id: string
  guess_date: string | null
  // Redacted (null) until this round has been answered.
  actual_date: string | null
  days_off: number | null
  score_delta: number | null
}

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

export type RoundOut = MoreOrLessRoundOut | GeoguessrRoundOut | DateguessrRoundOut | ImmichdleRoundOut

export interface GameOut {
  id: string
  type: string
  mode: string
  score: number
  finished: boolean
  rounds: RoundOut[]
  // Only ever populated for a finished Immichdle game - the mystery person is revealed once the
  // game is over, win or lose. null for every other game/mode and for an in-progress Immichdle game.
  target_person_id?: string | null
  target_person_name?: string | null
}

// No game_type here (unlike RoundOut) - game_id already fixes a round's game/mode server-side, so
// the guess body only needs the guess itself; see backend/src/api/schemas.py's parse_guess.
export interface MoreOrLessPlayRoundIn {
  guess: MoreOrLessGuess
}

export interface GeoguessrPlayRoundIn {
  latitude: number
  longitude: number
}

export interface DateguessrPlayRoundIn {
  date: string
}

export interface ImmichdlePlayRoundIn {
  person_id: string
}

// The four guess bodies share one endpoint (POST /games/{id}/rounds/{roundId}) - see playRound in
// api/games.ts. Which one is valid is fixed by the game's type/mode server-side, not restated here.
export type PlayRoundIn = MoreOrLessPlayRoundIn | GeoguessrPlayRoundIn | DateguessrPlayRoundIn | ImmichdlePlayRoundIn

export interface PlayRoundOut {
  // Binary-guess concept (MoreOrLess) - null for games with a continuous score (Geoguessr).
  correct: boolean | null
  score_delta: number
  score: number
  finished: boolean
  // The just-answered round, with its answer now revealed.
  answered_round: RoundOut
  next_round: RoundOut | null
}

// Mirrors backend/src/api/auth_schemas.py - own accounts (roadmap point B), unrelated to Immich's
// own users and, for now, to the anonymous X-Owner-Id used by games (see api/ownerId.ts).
export interface User {
  id: string
  email: string
  username: string
  full_name: string
  created_at: string
}

export interface RegisterIn {
  email: string
  username: string
  full_name: string
  password: string
}

export interface LoginIn {
  email: string
  password: string
}

// Reusable across features (not just Immichdle's guess input) - see backend/src/api/api.py's
// /persons/search.
export interface PersonSearchResultOut {
  id: string
  name: string
}

export interface PersonSearchOut {
  results: PersonSearchResultOut[]
}
