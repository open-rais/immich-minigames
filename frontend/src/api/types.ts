// Mirrors backend/src/api/schemas.py - keep field names in sync with that file.

export type Guess = "more" | "less"

export interface CreateGameIn {
  type: string
  mode: string
}

export interface MoreOrLessRoundOut {
  game_type: "more-or-less"
  id: string
  round_index: number
  reference_id: string
  reference_name: string
  reference_asset_count: number
  candidate_id: string
  candidate_name: string
  // Redacted (null) until this round has been answered.
  candidate_asset_count: number | null
  guess: Guess | null
  correct: boolean | null
}

export interface GeoguessrRoundOut {
  game_type: "geoguessr"
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
  game_type: "dateguessr"
  id: string
  round_index: number
  asset_id: string
  guess_date: string | null
  // Redacted (null) until this round has been answered.
  actual_date: string | null
  days_off: number | null
  score_delta: number | null
}

export type RoundOut = MoreOrLessRoundOut | GeoguessrRoundOut | DateguessrRoundOut

export interface GameOut {
  id: string
  type: string
  mode: string
  score: number
  finished: boolean
  rounds: RoundOut[]
}

// No game_type here (unlike RoundOut) - game_id already fixes a round's game/mode server-side, so
// the guess body only needs the guess itself; see backend/src/api/schemas.py's parse_guess.
export interface MoreOrLessPlayRoundIn {
  guess: Guess
}

export interface GeoguessrPlayRoundIn {
  latitude: number
  longitude: number
}

export interface DateguessrPlayRoundIn {
  date: string
}

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
