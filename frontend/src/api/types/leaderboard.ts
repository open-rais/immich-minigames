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

// Same entry shape as the normal LeaderboardOut plus a streak, scoped to one specific day's
// challenge instead of a rolling window. The streak is null on any date other than today - the
// backend only computes it for the current day, since that's the only one showing the badge.
export interface DailyLeaderboardEntryOut extends LeaderboardEntryOut {
  streak: number | null
}

export interface DailyLeaderboardOut {
  date: string
  entries: DailyLeaderboardEntryOut[]
}
