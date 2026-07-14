import i18n from "i18next"
import { initReactI18next } from "react-i18next"

import en from "./locales/en.json"
import es from "./locales/es.json"

const STORAGE_KEY = "minigames-lang"

function readStoredLanguage(): "en" | "es" {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === "es" ? "es" : "en"
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    es: { translation: es },
  },
  lng: readStoredLanguage(),
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
})

export default i18n
