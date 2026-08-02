import { apiClient } from "./client"
import type { GameOut } from "./types/common"
import type { DailyStatusOut } from "./types/daily"
import type { DailyLeaderboardOut } from "./types/leaderboard"

// backend/src/api/daily_api.py. Login is mandatory for every route, so no anonymous-vs-account
// branching to note here anymore.

export async function getDailyStatus(): Promise<DailyStatusOut> {
  const { data } = await apiClient.get<DailyStatusOut>("/daily")
  return data
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
