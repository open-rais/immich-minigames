import { createContext } from "react"

import type { LoginIn, RegisterIn, User } from "../api/types"

// Own account session (roadmap point B) - entirely separate from the anonymous X-Owner-Id used by
// games (see api/ownerId.ts). The backend holds the session as an httpOnly JWT cookie; this
// context just tracks who (if anyone) it currently belongs to for the UI. Split from
// AuthProvider.tsx/useAuth.ts so each of those files exports only what it's named for (keeps
// oxlint's react-refresh/only-export-components rule happy).
export interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (body: LoginIn) => Promise<User>
  register: (body: RegisterIn) => Promise<User>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
