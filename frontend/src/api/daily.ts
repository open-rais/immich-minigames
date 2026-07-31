import { apiClient } from "./client"
import type { GameOut } from "./types/common"
import type { DailyStatusOut } from "./types/daily"
import type { DailyLeaderboardOut } from "./types/leaderboard"

// Roadmap #G - backend/src/api/daily_api.py. Login is mandatory for every route (roadmap #H), so
// no anonymous-vs-account branching to note here anymore.

// Dedupes concurrent callers (menu + the game it navigates into both ask for this on mount) onto
// a single in-flight request. Cleared as soon as it settles, so it never serves stale data.
let dailyStatusInFlight: Promise<DailyStatusOut> | null = null

export async function getDailyStatus(): Promise<DailyStatusOut> {
  if (!dailyStatusInFlight) {
    dailyStatusInFlight = apiClient
      .get<DailyStatusOut>("/daily")
      .then(({ data }) => data)
      .finally(() => {
        dailyStatusInFlight = null
      })
  }
  return dailyStatusInFlight
}

export async function createDailyGame(gameType: string, mode: string): Promise<GameOut> {
  const { data } = await apiClient.post<GameOut>(`/daily/${gameType}/${mode}/games`)
  return data
}

// `date` as YYYY-MM-DD, defaults to today server-side when omitted.
export async function getDailyLeaderboard(
  gameType: string,
  mode: string,
  date?: string,
): Promise<DailyLeaderboardOut> {
  const { data } = await apiClient.get<DailyLeaderboardOut>(
    `/daily/${gameType}/${mode}/leaderboard`,
    {
      params: date ? { date } : undefined,
    },
  )
  return data
}
