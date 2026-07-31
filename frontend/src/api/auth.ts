import { apiClient } from "./client"
import type {
  ChangePasswordIn,
  LoginIn,
  RegisterIn,
  ResetPasswordIn,
  UpdateProfileIn,
  User,
} from "./types/auth"

// The backend sets/clears the session as an httpOnly cookie (see backend/src/api/auth_api.py) -
// same-origin in both dev (vite.config.ts's proxy) and prod (nginx.conf.template), so the browser
// attaches/receives it automatically, no token handling needed here.

export async function register(body: RegisterIn): Promise<User> {
  const { data } = await apiClient.post<User>("/auth/register", body)
  return data
}

// skipAuthRedirect (client.ts) - a wrong-password 401 here is normal control flow, shown inline on
// LoginPage, not "your session died" (the global 401 interceptor's concern - see AuthProvider.tsx).
export async function login(body: LoginIn): Promise<User> {
  const { data } = await apiClient.post<User>("/auth/login", body, { skipAuthRedirect: true })
  return data
}

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout")
}

// skipAuthRedirect (client.ts) - called on every mount by AuthProvider to check for an existing
// session; a 401 here just means "logged out", not an expired session to redirect away from.
export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me", { skipAuthRedirect: true })
  return data
}

export async function updateProfile(body: UpdateProfileIn): Promise<User> {
  const { data } = await apiClient.patch<User>("/auth/me", body)
  return data
}

// Roadmap #H, F0 - re-issues the session cookie in the same response (see backend/src/api/
// auth_api.py's change_password), so the caller's own session survives the password_changed_at
// bump that would otherwise revoke it. skipAuthRedirect (client.ts) - a wrong-current-password 401
// here is normal control flow, shown inline on ChangePasswordPage, same reasoning as login() above
// (without it, the global interceptor would redirect to /login before the inline error ever shows).
export async function changePassword(body: ChangePasswordIn): Promise<User> {
  const { data } = await apiClient.patch<User>("/auth/me/password", body, {
    skipAuthRedirect: true,
  })
  return data
}

// null clears the cosmetic skin - see backend/src/api/auth_api.py's update_skin.
export async function updateSkin(personId: string | null): Promise<User> {
  const { data } = await apiClient.put<User>("/auth/me/skin", { person_id: personId })
  return data
}

// Roadmap #H, F2 - the public counterpart of changePassword: no session to preserve (the caller is
// by definition logged out), so no cookie comes back - ResetPasswordPage.tsx sends them to /login
// afterward. No skipAuthRedirect needed either: this route has no auth dependency, so it can never
// 401 in the first place.
export async function resetPassword(body: ResetPasswordIn): Promise<void> {
  await apiClient.post("/auth/reset-password", body)
}
