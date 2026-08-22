import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router-dom"

import { getReportCounts } from "../api/reports"

// The entry point to /admin/reports from AdminPage.tsx - a plain link card (not a SettingAccordion:
// reports get their own page, not an inline expand), same outer card classes as
// SettingAccordion.tsx's top-level (non-nested) wrapper so it reads as a sibling of the accordions
// above/below it. The count badge (same pill as DailyLeaderboardPage.tsx's streak badge) only shows
// once loaded and non-zero - it's a "heads up, something's open" nudge, not meant to draw attention
// when there's nothing to review.
export function AdminReportsLink() {
  const { t } = useTranslation()
  const [total, setTotal] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    getReportCounts()
      .then((counts) => {
        if (!cancelled) setTotal(counts.asset + counts.person + counts.album)
      })
      .catch(() => {
        if (!cancelled) setTotal(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <Link
      to="/admin/reports"
      className="mt-4 flex items-center justify-between gap-3 rounded-2xl border-2 border-primary/20 px-6 py-4 text-start transition-colors hover:bg-hover-tint"
    >
      <div className="min-w-0">
        <h2 className="font-medium text-primary">{t("admin.reports.title")}</h2>
        <p className="mt-1 text-sm text-muted">{t("admin.reports.description")}</p>
      </div>
      {total !== null && total > 0 && (
        <span className="flex-none rounded-full bg-badge-bg px-2.5 py-1.5 font-mono text-xs leading-none font-bold text-badge-value">
          {total}
        </span>
      )}
    </Link>
  )
}
