// Roadmap #G - daily games, player-facing status. Mirrors backend/src/api/dto/daily.py (see
// services/games_service.py's GamesService.get_daily_status).

export type DailyModeStatusValue = "not_played" | "in_progress" | "finished"

export interface DailyModeStatusOut {
  game_type: string
  mode: string
  status: DailyModeStatusValue
  game_id: string | null
  score: number | null
}

export interface DailyStatusOut {
  // ISO datetimes (server time) - the countdown ticks off their offset rather than trusting the
  // client's own clock alone (see menu/DailyCountdown.tsx).
  resets_at: string
  server_now: string
  modes: DailyModeStatusOut[]
}
