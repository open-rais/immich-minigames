// Timeline's request/response DTOs - mirrors backend/src/api/dto/timeline.py.

import type { GameType } from "./common"

// A card already on the board - always fully revealed (see docs/TODO/TIMELINE.md decision [H]).
export interface TimelineCardOut {
  asset_id: string
  date: string
}

export interface TimelineRoundOut {
  game_type: typeof GameType.Timeline
  id: string
  round_index: number
  board: TimelineCardOut[]
  card_asset_id: string
  guess_slot: number | null
  // Redacted (null) until this round has been answered - it IS the answer.
  card_date: string | null
  correct_slot: number | null
  correct: boolean | null
  score_delta: number | null
}

// slot is the insertion index into the pending round's board (list.insert(i, x) semantics) - see
// backend/src/api/dto/timeline.py's TimelinePlayRoundIn.
export interface TimelinePlayRoundIn {
  slot: number
}
