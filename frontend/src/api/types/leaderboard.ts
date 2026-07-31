// Leaderboards (requires login, unlike the personal records in records.ts) -
// mirrors backend/src/api/dto/leaderboard.py.

export type LeaderboardWindow = "all" | "weekly" | "daily"

export interface LeaderboardEntryOut {
  rank: number
  username: string
  skin_person_id: string | null
  best_score: number
}

export interface LeaderboardOut {
  window: LeaderboardWindow
  entries: LeaderboardEntryOut[]
}

// Same entry shape as the normal LeaderboardOut, scoped to one specific day's
// challenge instead of a rolling window.
export interface DailyLeaderboardOut {
  date: string
  entries: LeaderboardEntryOut[]
}
