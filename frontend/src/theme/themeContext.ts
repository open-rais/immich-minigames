import { createContext } from "react"

// Split from ThemeProvider.tsx/useTheme.ts so each file exports only what it's named for (keeps
// oxlint's react-refresh/only-export-components rule happy) - same convention as auth/authContext.ts.
export type ThemePreference = "light" | "dark" | "system"
export type ResolvedTheme = "light" | "dark"

export interface ThemeContextValue {
  preference: ThemePreference
  resolved: ResolvedTheme
  setPreference: (preference: ThemePreference) => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)
