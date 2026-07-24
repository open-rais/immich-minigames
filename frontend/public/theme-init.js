// Keep in sync with STORAGE_KEY in src/theme/ThemeProvider.tsx. Runs synchronously before any
// stylesheet/JS, so the correct .dark/.light class is on <html> before first paint - avoids a
// flash of the wrong theme. Mirrors Immich's own web app (class-on-<html> + localStorage), minus
// its JSON.parse quirk since we store a plain string, not JSON.
//
// A static file (not inline in index.html) so nginx's Content-Security-Policy can use a plain
// script-src 'self' without 'unsafe-inline' (docs/TODO/CODE-REVIEW.md #13).
;(function () {
  var KEY = "minigames-theme"
  var stored = localStorage.getItem(KEY)
  var preference = stored === "light" || stored === "dark" ? stored : "system"
  var resolved =
    preference === "system"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : preference
  document.documentElement.classList.add(resolved)
})()
