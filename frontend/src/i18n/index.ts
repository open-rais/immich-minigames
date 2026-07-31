import i18n from "i18next"
import { initReactI18next } from "react-i18next"

const STORAGE_KEY = "minigames-lang"

export type Language = "en" | "es"

function readStoredLanguage(): Language {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === "es" ? "es" : "en"
}

// Loaded via import() instead of a static top-level import (CODE-REVIEW-FRONT.md B-2) - with two
// languages the saving is noise, but the roadmap already plans French/German (point i), and at 4
// languages loading all of them upfront to use one stops being noise. `loaded` dedupes repeat calls
// (e.g. switching back to a language already loaded once this session).
const loaders: Record<Language, () => Promise<{ default: Record<string, unknown> }>> = {
  en: () => import("./locales/en.json"),
  es: () => import("./locales/es.json"),
}
const loaded = new Set<Language>()

export async function loadLanguage(lang: Language): Promise<void> {
  if (loaded.has(lang)) return
  const { default: resources } = await loaders[lang]()
  i18n.addResourceBundle(lang, "translation", resources)
  loaded.add(lang)
}

const initialLanguage = readStoredLanguage()

// Resolved once the initial language's bundle is loaded and i18next is initialized - main.tsx
// waits on this before its first render, so there's no flash of untranslated keys.
export const i18nReady = loadLanguage(initialLanguage).then(() =>
  i18n.use(initReactI18next).init({
    lng: initialLanguage,
    fallbackLng: "en",
    interpolation: {
      escapeValue: false,
    },
  }),
)

export default i18n
