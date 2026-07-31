import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router-dom"

import { SegmentedControl } from "../games/shared/SegmentedControl"
import i18n, { loadLanguage } from "../i18n"
import type { ThemePreference } from "../theme/themeContext"
import { useTheme } from "../theme/useTheme"

// Language names are NOT run through i18next on purpose - a language's own display name
// shouldn't change depending on which language is currently active (same reason browsers/OSes
// show language pickers untranslated).
const LANGUAGE_LABELS: Record<"en" | "es" | "fr" | "de", string> = {
  en: "English",
  es: "Español",
  fr: "Français",
  de: "Deutsch",
}

function BackArrowIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="block shrink-0"
    >
      <path d="M15 18l-6-6 6-6" />
    </svg>
  )
}

function LanguageSelector() {
  const current = (["en", "es", "fr", "de"].includes(i18n.language) ? i18n.language : "en") as "en" | "es" | "fr" | "de"

  function handleChange(lang: "en" | "es" | "fr" | "de") {
    // Loaded on demand (see i18n/index.ts) - awaited here so switching to a
    // language not loaded yet doesn't flash the fallback language while its bundle fetches.
    void loadLanguage(lang).then(() => {
      localStorage.setItem("minigames-lang", lang)
      i18n.changeLanguage(lang)
    })
  }

  return (
    <select
      value={current}
      onChange={(e) => handleChange(e.target.value as "en" | "es" | "fr" | "de")}
      className="h-11 w-full cursor-pointer rounded-xl border border-line-soft bg-surface px-3.5 text-[15px] font-semibold text-ink outline-none transition-colors hover:bg-hover-tint focus:border-primary"
    >
      {(["en", "es", "fr", "de"] as const).map((lang) => (
        <option key={lang} value={lang}>
          {LANGUAGE_LABELS[lang]}
        </option>
      ))}
    </select>
  )
}

function ThemeSelector() {
  const { t } = useTranslation()
  const { preference, setPreference } = useTheme()
  const options: { value: ThemePreference; label: string }[] = [
    { value: "light", label: t("settings.themeOptions.light") },
    { value: "dark", label: t("settings.themeOptions.dark") },
    { value: "system", label: t("settings.themeOptions.system") },
  ]
  return <SegmentedControl options={options} value={preference} onChange={setPreference} size="lg" />
}

function SettingCard({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="mt-4 rounded-2xl border border-line bg-surface p-5">
      <p className="mb-2 text-xs font-semibold tracking-wide text-faint uppercase">{label}</p>
      {children}
    </div>
  )
}

// Standalone settings page (roadmap #g) - language/theme controls moved here out of
// menu/UserMenu.tsx's popover, which now just links to this page. Same page shell as
// admin/AdminPage.tsx (sticky header + back link, max-w-3xl main) so it reads as a peer page.
export function SettingsPage() {
  const { t } = useTranslation()

  return (
    <div className="min-h-screen bg-app-bg">
      <header className="sticky top-0 z-10 border-b border-line bg-surface pt-[env(safe-area-inset-top)]">
        <div className="flex h-16 items-center px-6 md:px-10">
          <Link
            to="/"
            className="flex items-center gap-2 rounded-full py-2 pr-3 pl-2 text-sm font-semibold text-body transition-colors hover:bg-hover-tint"
          >
            <BackArrowIcon />
            {/* Optical alignment nudge - see admin/AdminPage.tsx's identical back link. */}
            <span className="translate-y-[1px]">{t("common.back")}</span>
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8 md:px-10">
        <h1 className="text-2xl font-bold text-ink">{t("settings.title")}</h1>

        <SettingCard label={t("settings.language")}>
          <LanguageSelector />
        </SettingCard>
        <SettingCard label={t("settings.theme")}>
          <ThemeSelector />
        </SettingCard>
      </main>
    </div>
  )
}
