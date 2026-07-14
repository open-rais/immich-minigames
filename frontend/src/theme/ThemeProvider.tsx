import { useCallback, useEffect, useState } from "react"
import type { ReactNode } from "react"

import { ThemeContext } from "./themeContext"
import type { ResolvedTheme, ThemePreference } from "./themeContext"

// Keep in sync with the inline script in index.html, which sets the initial .dark/.light class
// on <html> before first paint (avoiding a flash of the wrong theme) - this key must match.
const STORAGE_KEY = "minigames-theme"

function readStoredPreference(): ThemePreference {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === "light" || stored === "dark" ? stored : "system"
}

function resolveFromSystem(): ResolvedTheme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

function applyResolvedClass(resolved: ResolvedTheme) {
  const root = document.documentElement
  root.classList.remove("light", "dark")
  root.classList.add(resolved)
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(readStoredPreference)
  // Lazy initializer reads the class index.html's inline script already applied - React never
  // independently re-decides light/dark for the initial render, it only observes what's already
  // on <html>, so there's no chance of a second, React-caused flash.
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    document.documentElement.classList.contains("dark") ? "dark" : "light",
  )

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next)
    if (next === "system") {
      localStorage.removeItem(STORAGE_KEY)
    } else {
      localStorage.setItem(STORAGE_KEY, next)
    }
    const nextResolved = next === "system" ? resolveFromSystem() : next
    applyResolvedClass(nextResolved)
    setResolved(nextResolved)
  }, [])

  // Live-react to OS-level scheme changes only while following the system preference.
  useEffect(() => {
    if (preference !== "system") return
    const mql = window.matchMedia("(prefers-color-scheme: dark)")
    function handleChange(e: MediaQueryListEvent) {
      const next: ResolvedTheme = e.matches ? "dark" : "light"
      applyResolvedClass(next)
      setResolved(next)
    }
    mql.addEventListener("change", handleChange)
    return () => mql.removeEventListener("change", handleChange)
  }, [preference])

  return <ThemeContext.Provider value={{ preference, resolved, setPreference }}>{children}</ThemeContext.Provider>
}
