import { useTranslation } from "react-i18next"
import { Link, Navigate } from "react-router-dom"

import { ReportEntity } from "../api/types/reports"
import { useAuth } from "../auth/useAuth"
import { AdminReportsList } from "./AdminReportsList"

// Same back-arrow glyph as AdminPage.tsx - not shared, this is the only other admin page and the
// icon is a few lines of inline SVG, not worth a shared import for.
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

// The three stacked report lists (asset/person/album) - see AdminReportsList.tsx. Stacked, not in
// three columns: the scrollable-box pattern already used for users/invites works the same on
// mobile and desktop, three columns wouldn't.
export function AdminReportsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()

  if (!user) return null
  if (!user.is_admin) return <Navigate to="/" replace />

  return (
    <div className="min-h-screen bg-app-bg">
      <header className="sticky top-0 z-10 border-b border-line bg-surface pt-[env(safe-area-inset-top)]">
        <div className="flex h-16 items-center px-6 md:px-10">
          <Link
            to="/admin"
            className="flex items-center gap-2 rounded-full py-2 pr-3 pl-2 text-sm font-semibold text-body transition-colors hover:bg-hover-tint"
          >
            <BackArrowIcon />
            <span className="translate-y-[1px]">{t("common.back")}</span>
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8 md:px-10">
        <h1 className="text-2xl font-bold text-ink">{t("admin.reports.title")}</h1>

        <section className="mt-6">
          <h2 className="font-medium text-primary">{t("admin.reports.sections.asset")}</h2>
          <div className="mt-3">
            <AdminReportsList entityType={ReportEntity.Asset} />
          </div>
        </section>

        <section className="mt-8">
          <h2 className="font-medium text-primary">{t("admin.reports.sections.person")}</h2>
          <div className="mt-3">
            <AdminReportsList entityType={ReportEntity.Person} />
          </div>
        </section>

        <section className="mt-8">
          <h2 className="font-medium text-primary">{t("admin.reports.sections.album")}</h2>
          <div className="mt-3">
            <AdminReportsList entityType={ReportEntity.Album} />
          </div>
        </section>
      </main>
    </div>
  )
}
