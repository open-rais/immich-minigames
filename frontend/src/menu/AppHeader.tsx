import { useTranslation } from "react-i18next"
import { Link } from "react-router-dom"

import { useAuth } from "../auth/useAuth"

// Same bar shape as Immich's own top header (height/padding/border) - no icon yet (one is planned
// for later), no search bar/upload/notifications since those features don't exist here yet. The
// right side now carries auth state (roadmap point B): just a "Log in" link when signed out (sign
// up lives one click away, from LoginPage's own footer - see AuthCard - so the header doesn't need
// its own signup link), or the username (linking to /profile) when signed in - logout itself lives
// on the profile page, not here, to keep this bar minimal.
//
// The white background extends up through `env(safe-area-inset-top)` (needs `viewport-fit=cover`
// in index.html's viewport meta) so it fills the notch/Dynamic Island area on iPhone instead of
// leaving a gap of app-bg color above the bar - the visible h-16 row stays centered below that.
export function AppHeader() {
  const { t } = useTranslation()
  const { user, loading } = useAuth()

  return (
    <header className="border-b border-line bg-white pt-[env(safe-area-inset-top)]">
      <div className="flex h-16 items-center justify-between px-6 md:px-10">
        <span className="text-xl font-bold text-ink">{t("appHeader.title")}</span>
        {!loading && (
          <nav className="flex items-center gap-4 text-sm font-semibold">
            {user ? (
              <Link to="/profile" className="text-body hover:text-primary">
                {user.username}
              </Link>
            ) : (
              <Link to="/login" className="text-body hover:text-primary">
                {t("auth.login.cta")}
              </Link>
            )}
          </nav>
        )}
      </div>
    </header>
  )
}
