// Dateguessr's request/response DTOs - mirrors backend/src/api/dto/dateguessr.py.

import type { GameType } from "./common"

export interface DateguessrRoundOut {
  game_type: typeof GameType.Dateguessr
  id: string
  round_index: number
  // Main ("answer") asset first, then up to 4 decorative extras.
  asset_ids: string[]
  guess_date: string | null
  // Redacted (null) until this round has been answered.
  actual_date: string | null
  days_off: number | null
  score_delta: number | null
}

export interface DateguessrPlayRoundIn {
  date: string
}
