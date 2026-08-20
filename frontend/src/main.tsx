import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "./index.css"
import { i18nReady } from "./i18n"
import { registerServiceWorker } from "./pwa/register"
import App from "./App.tsx"

registerServiceWorker()

// Waits for the active language's bundle (loaded via import(), see i18n/index.ts) instead of
// rendering immediately - otherwise the first paint would flash raw translation keys.
i18nReady.then(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})
