import { useTranslation } from "react-i18next"
import { Link, Navigate } from "react-router-dom"

import { useAuth } from "../auth/useAuth"
import { AdminGamesSection } from "./AdminGamesSection"
import { AdminUsersSection } from "./AdminUsersSection"
import { SettingAccordion } from "./SettingAccordion"

function BackArrowIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" className="block shrink-0">
      <path d="M15 18l-6-6 6-6" />
    </svg>
  )
}

// Visual reference: the user's own Immich instance's /admin/system-settings (immich-admin-front.png/
// .htm, plus basic.png where they relabeled one of Immich's own setting cards to show exactly this
// shape - stacked SettingAccordion cards, "Juegos" expanding into one nested, icon-less accordion
// per game). No left sidebar - unlike Immich's Users/Jobs/Settings split (separate pages), our two
// categories are both accordions on this one page, matching what the user asked for directly.
export function AdminPage() {
  const { t } = useTranslation()
  const { user, loading } = useAuth()

  if (!loading && !user) return <Navigate to="/login" replace />
  if (!loading && user && !user.is_admin) return <Navigate to="/" replace />
  if (!user) return null

  return (
    <div className="min-h-screen bg-app-bg">
      <header className="sticky top-0 z-10 border-b border-line bg-surface pt-[env(safe-area-inset-top)]">
        <div className="flex h-16 items-center px-6 md:px-10">
          <Link to="/" className="flex items-center gap-2 rounded-full py-2 pr-3 pl-2 text-sm font-semibold text-body transition-colors hover:bg-hover-tint">
            <BackArrowIcon />
            {/* "Back"/"Volver" have no descenders, so their glyphs sit in the top portion of the
                text line box - centering that box against the (fully symmetric) icon box via
                items-center alone still reads as "text sits higher than the icon". Nudge the text
                down slightly to align their optical centers instead of their box centers. */}
            <span className="translate-y-[1px]">{t("common.back")}</span>
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8 md:px-10">
        <SettingAccordion title={t("admin.users.title")} description={t("admin.users.description")}>
          <AdminUsersSection />
        </SettingAccordion>

        <SettingAccordion title={t("admin.games.title")} description={t("admin.games.description")}>
          <AdminGamesSection />
        </SettingAccordion>
      </main>
    </div>
  )
}
