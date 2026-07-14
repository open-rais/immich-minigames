import { useContext } from "react"

import { ThemeContext } from "./themeContext"
import type { ThemeContextValue } from "./themeContext"

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider")
  return ctx
}
