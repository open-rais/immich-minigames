// Mirrors backend/src/api/schemas.py - keep field names in sync with that file.

export type Guess = "more" | "less"

export interface CreateGameIn {
  type: string
  mode: string
}

export interface RoundOut {
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

export interface GameOut {
  id: string
  type: string
  mode: string
  score: number
  finished: boolean
  rounds: RoundOut[]
}

export interface PlayRoundIn {
  guess: Guess
}

export interface PlayRoundOut {
  correct: boolean
  score_delta: number
  score: number
  finished: boolean
  // The just-answered round, with candidate_asset_count now revealed.
  answered_round: RoundOut
  next_round: RoundOut | null
}
