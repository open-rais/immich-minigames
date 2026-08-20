import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"

import { listReports } from "../api/reports"
import type { AdminReportOut, ReportEntity } from "../api/types/reports"
import { AdminReportRow } from "./AdminReportRow"
import { useInfiniteAdminList } from "./useInfiniteAdminList"

interface AdminReportsListProps {
  entityType: ReportEntity
}

// One entity_type's paginated report list (one of the three stacked sections in
// AdminReportsPage.tsx) - infinite-scroll paginated (see useInfiniteAdminList.ts), same ~5-row
// scroll box convention as AdminInvitesSection.tsx.
export function AdminReportsList({ entityType }: AdminReportsListProps) {
  const { t } = useTranslation()
  const [solved, setSolved] = useState(false)
  const {
    items: reports,
    error,
    loadingMore,
    containerRef,
    onScroll,
    setItems: setReports,
    reload,
  } = useInfiniteAdminList<AdminReportOut>((offset, limit) =>
    listReports(entityType, solved, { offset, limit }),
  )

  // useInfiniteAdminList only fetches page 1 on its own mount - changing `solved` needs an
  // explicit reload(). Skips the first render so this doesn't duplicate that initial fetch.
  const isFirstRender = useRef(true)
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }
    reload()
    // reload isn't stable across renders (see useInfiniteAdminList.ts); only `solved` changing
    // should retrigger this, same reasoning as that hook's own mount-only effect.
    // oxlint-disable-next-line
  }, [solved])

  function handleResolved(updated: AdminReportOut) {
    setReports((prev) => prev?.map((r) => (r.id === updated.id ? updated : r)) ?? prev)
  }

  return (
    <div>
      <label className="flex items-center gap-2.5 text-sm font-semibold text-body">
        <input
          type="checkbox"
          checked={solved}
          onChange={(e) => setSolved(e.target.checked)}
          className="h-4 w-4 accent-primary"
        />
        {t("admin.reports.showSolved")}
      </label>

      {error && <p className="mt-3 text-sm font-semibold text-rose-600">{error}</p>}

      {!reports ? (
        <p className="mt-3 text-sm text-faint">{t("admin.reports.loading")}</p>
      ) : reports.length === 0 ? (
        <p className="mt-3 text-sm text-faint">{t("admin.reports.empty")}</p>
      ) : (
        <div
          ref={containerRef}
          onScroll={onScroll}
          className="mt-3 max-h-[350px] overflow-y-auto overscroll-contain"
        >
          {reports.map((report) => (
            <AdminReportRow key={report.id} report={report} onResolved={handleResolved} />
          ))}
          {loadingMore && <p className="mt-2 text-sm text-faint">{t("admin.reports.loading")}</p>}
        </div>
      )}
    </div>
  )
}
