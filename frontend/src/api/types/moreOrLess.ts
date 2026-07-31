// MoreOrLess's request/response DTOs - mirrors backend/src/api/dto/more_or_less.py.

import type { GameType } from "./common"

export type MoreOrLessGuess = "more" | "less"

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

// No game_type here (unlike RoundOut) - game_id already fixes a round's game/mode server-side, so
// the guess body only needs the guess itself; see backend/src/api/dto/common.py's parse_guess.
export interface MoreOrLessPlayRoundIn {
  guess: MoreOrLessGuess
}
