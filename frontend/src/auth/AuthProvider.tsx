import axios from "axios"
import { useEffect, useState } from "react"
import type { ReactNode } from "react"
import { useNavigate } from "react-router-dom"

import {
  changePassword as apiChangePassword,
  getMe,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  updateProfile as apiUpdateProfile,
  updateSkin as apiUpdateSkin,
} from "../api/auth"
import { apiClient } from "../api/client"
import type { ChangePasswordIn, LoginIn, RegisterIn, UpdateProfileIn, User } from "../api/types"
import { AuthContext } from "./authContext"
import { setPendingRedirectFrom } from "./pendingRedirect"

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    // A 401 here just means "no one is logged in" - not an error to surface.
    getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  // Roadmap #H, F0 - a session that dies mid-use (expired, or revoked by a password change on
  // another device) surfaces as a 401 on whatever request happens to be in flight next; catch it
  // globally here rather than in every screen that calls the API. login/getMe opt out via
  // skipAuthRedirect (see client.ts) - their 401s are normal control flow, handled locally.
  // window.location.pathname (not a captured useLocation() value) since this effect only runs
  // once, so a captured location would go stale on every navigation after the first. The
  // destination is stashed via setPendingRedirectFrom (pendingRedirect.ts), not navigate's own
  // `state` - see that file for why: every already-mounted protected page's own
  // `!user -> Navigate to /login` guard also fires once setUser(null) below takes effect, and its
  // state-less navigate call would otherwise clobber this one's.
  useEffect(() => {
    const id = apiClient.interceptors.response.use(
      (response) => response,
      (error: unknown) => {
        if (axios.isAxiosError(error) && error.response?.status === 401 && !error.config?.skipAuthRedirect) {
          setPendingRedirectFrom(window.location.pathname)
          setUser(null)
          navigate("/login", { replace: true })
        }
        return Promise.reject(error)
      },
    )
    return () => apiClient.interceptors.response.eject(id)
  }, [navigate])

  async function login(body: LoginIn) {
    const loggedInUser = await apiLogin(body)
    setUser(loggedInUser)
    return loggedInUser
  }

  async function register(body: RegisterIn) {
    const registeredUser = await apiRegister(body)
    setUser(registeredUser)
    return registeredUser
  }

  async function logout() {
    await apiLogout()
    setUser(null)
  }

  async function updateProfile(body: UpdateProfileIn) {
    const updated = await apiUpdateProfile(body)
    setUser(updated)
    return updated
  }

  async function updateSkin(personId: string | null) {
    const updated = await apiUpdateSkin(personId)
    setUser(updated)
    return updated
  }

  async function changePassword(body: ChangePasswordIn) {
    const updated = await apiChangePassword(body)
    setUser(updated)
    return updated
  }

  return (
    <AuthContext.Provider
      value={{ user, loading, login, register, logout, updateProfile, updateSkin, changePassword }}
    >
      {children}
    </AuthContext.Provider>
  )
}
