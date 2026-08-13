import { apiClient } from "./client"
import type {
  CreateInviteOut,
  DailySettingsOut,
  GameSettingsOut,
  InviteOut,
  UpdateDailySettingsIn,
} from "./types/admin"
import type { UpdateProfileIn, User } from "./types/auth"

// Same request shapes as api/auth.ts's self-service updateProfile/updateSkin, applied to an
// arbitrary userId instead of the caller's own account. Backend enforces is_admin on every route
// here (see backend/src/api/admin_api.py).

// Paginated (roadmap infinite-scroll UI, see admin/useInfiniteAdminList.ts) - same offset/limit
// convention as api/games.ts's searchPersons.
export async function listUsers(opts?: { offset?: number; limit?: number }): Promise<User[]> {
  const { data } = await apiClient.get<User[]>("/admin/users", {
    params: { offset: opts?.offset, limit: opts?.limit },
  })
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

// backend/src/api/admin_api.py's create_password_reset. Same response shape as
// createInvite below (id/token/expires_at) - the token is only ever available here, shown once via
// ShareModal (see admin/AdminUserRow.tsx).
export async function createPasswordReset(userId: string): Promise<CreateInviteOut> {
  const { data } = await apiClient.post<CreateInviteOut>(`/admin/users/${userId}/password-reset`)
  return data
}

// backend/src/api/admin_games_api.py.

// Shared with admin/AdminGamesSection.tsx, which optimistically updates this cache entry when the
// admin saves/resets a mode's settings.
export const GAME_SETTINGS_KEY = "game-settings"

export async function listGameSettings(): Promise<GameSettingsOut[]> {
  const { data } = await apiClient.get<GameSettingsOut[]>("/admin/games/settings")
  return data
}

export async function updateGameSettings(
  gameType: string,
  mode: string,
  values: Record<string, number>,
): Promise<GameSettingsOut> {
  const { data } = await apiClient.put<GameSettingsOut>(
    `/admin/games/${gameType}/${mode}/settings`,
    values,
  )
  return data
}

export async function resetGameSettings(gameType: string, mode: string): Promise<GameSettingsOut> {
  const { data } = await apiClient.post<GameSettingsOut>(
    `/admin/games/${gameType}/${mode}/settings/reset`,
  )
  return data
}

// backend/src/api/admin_daily_api.py.

// Shared with admin/AdminGamesSection.tsx, which optimistically updates this cache entry when the
// admin saves/resets a mode's daily config.
export const DAILY_SETTINGS_KEY = "daily-settings"

export async function listDailySettings(): Promise<DailySettingsOut[]> {
  const { data } = await apiClient.get<DailySettingsOut[]>("/admin/daily/settings")
  return data
}

export async function updateDailySettings(
  gameType: string,
  mode: string,
  body: UpdateDailySettingsIn,
): Promise<DailySettingsOut> {
  const { data } = await apiClient.put<DailySettingsOut>(`/admin/daily/${gameType}/${mode}`, body)
  return data
}

export async function resetDailySettings(
  gameType: string,
  mode: string,
): Promise<DailySettingsOut> {
  const { data } = await apiClient.post<DailySettingsOut>(`/admin/daily/${gameType}/${mode}/reset`)
  return data
}

// backend/src/api/admin_invites_api.py.

export async function createInvite(): Promise<CreateInviteOut> {
  const { data } = await apiClient.post<CreateInviteOut>("/admin/invites")
  return data
}

// Paginated (roadmap infinite-scroll UI, see admin/useInfiniteAdminList.ts) - same offset/limit
// convention as api/games.ts's searchPersons.
export async function listInvites(opts?: {
  offset?: number
  limit?: number
}): Promise<InviteOut[]> {
  const { data } = await apiClient.get<InviteOut[]>("/admin/invites", {
    params: { offset: opts?.offset, limit: opts?.limit },
  })
  return data
}

export async function revokeInvite(inviteId: string): Promise<void> {
  await apiClient.delete(`/admin/invites/${inviteId}`)
}
