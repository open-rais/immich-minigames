import { apiClient } from "./client"
import type { GameSettingsOut, UpdateProfileIn, User } from "./types"

// Admin feature (ADMIN-FEATURE.md point #3) - same request shapes as api/auth.ts's self-service
// updateProfile/updateSkin, applied to an arbitrary userId instead of the caller's own account.
// Backend enforces is_admin on every route here (see backend/src/api/admin_api.py).

export async function listUsers(): Promise<User[]> {
  const { data } = await apiClient.get<User[]>("/admin/users")
  return data
}

export async function updateUser(userId: string, body: UpdateProfileIn): Promise<User> {
  const { data } = await apiClient.patch<User>(`/admin/users/${userId}`, body)
  return data
}

export async function updateUserSkin(userId: string, personId: string | null): Promise<User> {
  const { data } = await apiClient.put<User>(`/admin/users/${userId}/skin`, { person_id: personId })
  return data
}

// Admin feature (ADMIN-FEATURE.md point #4) - backend/src/api/admin_games_api.py.

export async function listGameSettings(): Promise<GameSettingsOut[]> {
  const { data } = await apiClient.get<GameSettingsOut[]>("/admin/games/settings")
  return data
}

export async function updateGameSettings(gameType: string, values: Record<string, number>): Promise<GameSettingsOut> {
  const { data } = await apiClient.put<GameSettingsOut>(`/admin/games/${gameType}/settings`, values)
  return data
}

export async function resetGameSettings(gameType: string): Promise<GameSettingsOut> {
  const { data } = await apiClient.post<GameSettingsOut>(`/admin/games/${gameType}/settings/reset`)
  return data
}
