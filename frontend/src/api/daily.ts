import { apiClient } from "./client"
import type { DailyLeaderboardOut, DailyStatusOut, GameOut } from "./types"

// Roadmap #G - backend/src/api/daily_api.py. All three work anonymously (see api/ownerId.ts's
// X-Owner-Id, attached by client.ts's request interceptor) - same as the normal leaderboard, only
// the *entries* are restricted to logged-in players, not the routes themselves.

export async function getDailyStatus(): Promise<DailyStatusOut> {
  const { data } = await apiClient.get<DailyStatusOut>("/daily")
  return data
}

export async function createDailyGame(gameType: string, mode: string): Promise<GameOut> {
  const { data } = await apiClient.post<GameOut>(`/daily/${gameType}/${mode}/games`)
  return data
}

// `date` as YYYY-MM-DD, defaults to today server-side when omitted.
export async function getDailyLeaderboard(gameType: string, mode: string, date?: string): Promise<DailyLeaderboardOut> {
  const { data } = await apiClient.get<DailyLeaderboardOut>(`/daily/${gameType}/${mode}/leaderboard`, {
    params: date ? { date } : undefined,
  })
  return data
}
