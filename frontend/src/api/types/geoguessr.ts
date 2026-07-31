// Geoguessr's request/response DTOs - mirrors backend/src/api/dto/geoguessr.py.

import type { GameType } from "./common"

export interface GeoguessrRoundOut {
  game_type: typeof GameType.Geoguessr
  id: string
  round_index: number
  // Main ("answer") asset first, then up to 4 decorative extras.
  asset_ids: string[]
  guess_latitude: number | null
  guess_longitude: number | null
  // Redacted (null) until this round has been answered.
  actual_latitude: number | null
  actual_longitude: number | null
  distance_km: number | null
  score_delta: number | null
}

export interface GeoguessrPlayRoundIn {
  latitude: number
  longitude: number
}
