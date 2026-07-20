import { apiClient } from "./client"
import type { UpdateProfileIn, User } from "./types"

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
