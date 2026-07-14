import { useEffect, useState } from "react"
import type { ReactNode } from "react"

import { getMe, login as apiLogin, logout as apiLogout, register as apiRegister } from "../api/auth"
import type { LoginIn, RegisterIn, User } from "../api/types"
import { AuthContext } from "./authContext"

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // A 401 here just means "no one is logged in" - not an error to surface.
    getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

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

  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>
}
