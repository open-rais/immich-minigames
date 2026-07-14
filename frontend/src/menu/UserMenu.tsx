import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useLocation } from "react-router-dom"

import { useAuth } from "../auth/useAuth"
import i18n from "../i18n"
import type { ThemePreference } from "../theme/themeContext"
import { useTheme } from "../theme/useTheme"

// Language names are NOT run through i18next on purpose - a language's own display name
// shouldn't change depending on which language is currently active (same reason browsers/OSes
// show language pickers untranslated).
const LANGUAGE_LABELS: Record<"en" | "es", string> = { en: "English", es: "Español" }

function UserIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-4.4 3.6-8 8-8s8 3.6 8 8" />
    </svg>
  )
}

function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div className="flex rounded-full bg-count-bg p-1">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`flex-1 rounded-full px-2 py-1 text-xs font-semibold transition-colors ${
            value === opt.value ? "bg-primary text-white" : "text-body hover:bg-hover-tint"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

function LanguageSelector() {
  const current = i18n.language === "es" ? "es" : "en"
  return (
    <SegmentedControl
      options={(["en", "es"] as const).map((lang) => ({ value: lang, label: LANGUAGE_LABELS[lang] }))}
      value={current}
      onChange={(lang) => {
        localStorage.setItem("minigames-lang", lang)
        i18n.changeLanguage(lang)
      }}
    />
  )
}

function ThemeSelector() {
  const { t } = useTranslation()
  const { preference, setPreference } = useTheme()
  const options: { value: ThemePreference; label: string }[] = [
    { value: "light", label: t("userMenu.themeOptions.light") },
    { value: "dark", label: t("userMenu.themeOptions.dark") },
    { value: "system", label: t("userMenu.themeOptions.system") },
  ]
  return <SegmentedControl options={options} value={preference} onChange={setPreference} />
}

// Replaces AppHeader's old inline "Log in"/username link with a circular trigger that opens a
// popover holding all 3 account-adjacent controls: the profile/login link, language, and theme -
// keeps the header bar itself minimal while giving each of those its own row instead of cramming
// them into the bar.
export function UserMenu() {
  const { t } = useTranslation()
  const { user, loading } = useAuth()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const location = useLocation()

  useEffect(() => {
    if (!open) return
    function handlePointerDown(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("pointerdown", handlePointerDown)
    document.addEventListener("keydown", handleKeyDown)
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown)
      document.removeEventListener("keydown", handleKeyDown)
    }
  }, [open])

  // Closes the popover on any route change (the profile/login row navigates via <Link>).
  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  if (loading) return null

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={t("userMenu.trigger")}
        aria-expanded={open}
        className="flex h-10 w-10 items-center justify-center rounded-full border border-line-strong bg-surface text-body shadow-card transition-colors hover:bg-hover-tint"
      >
        <UserIcon />
      </button>

      {open && (
        <div className="absolute top-[calc(100%+8px)] right-0 z-40 w-64 rounded-2xl border border-line bg-surface p-2 shadow-card">
          <Link to={user ? "/profile" : "/login"} className="block rounded-xl px-3 py-2.5 text-sm font-semibold text-body hover:bg-hover-tint">
            {user ? user.username : t("auth.login.cta")}
          </Link>
          <div className="my-1 border-t border-line" />
          <div className="px-3 py-2">
            <p className="mb-1.5 text-xs font-semibold tracking-wide text-faint uppercase">{t("userMenu.language")}</p>
            <LanguageSelector />
          </div>
          <div className="px-3 py-2">
            <p className="mb-1.5 text-xs font-semibold tracking-wide text-faint uppercase">{t("userMenu.theme")}</p>
            <ThemeSelector />
          </div>
        </div>
      )}
    </div>
  )
}
