import { createContext } from "react"

import type {
  ChangePasswordIn,
  LoginIn,
  RegisterIn,
  UpdateProfileIn,
  User,
} from "../api/types/auth"

// Own account session (roadmap point B). The backend holds the session as an httpOnly JWT cookie;
// this context just tracks who (if anyone) it currently belongs to for the UI. Split from
// AuthProvider.tsx/useAuth.ts so each of those files exports only what it's named for (keeps
// oxlint's react-refresh/only-export-components rule happy).
export interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (body: LoginIn) => Promise<User>
  register: (body: RegisterIn) => Promise<User>
  logout: () => Promise<void>
  // Profile edit page (roadmap point E) - both update the same account and refresh `user` with
  // the server's response, same pattern as login/register.
  updateProfile: (body: UpdateProfileIn) => Promise<User>
  updateSkin: (personId: string | null) => Promise<User>
  // Roadmap #H, F0 - change-password page (ChangePasswordPage.tsx), same refresh-from-response
  // pattern as updateProfile/updateSkin above.
  changePassword: (body: ChangePasswordIn) => Promise<User>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
