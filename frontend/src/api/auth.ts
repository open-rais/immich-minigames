import { apiClient } from "./client"
import type { LoginIn, RegisterIn, User } from "./types"

// The backend sets/clears the session as an httpOnly cookie (see backend/src/api/auth_api.py) -
// same-origin in both dev (vite.config.ts's proxy) and prod (nginx.conf.template), so the browser
// attaches/receives it automatically, no token handling needed here.

export async function register(body: RegisterIn): Promise<User> {
  const { data } = await apiClient.post<User>("/auth/register", body)
  return data
}

export async function login(body: LoginIn): Promise<User> {
  const { data } = await apiClient.post<User>("/auth/login", body)
  return data
}

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout")
}

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me")
  return data
}
