import { useState } from "react"
import { useTranslation } from "react-i18next"

import { apiErrorMessage } from "../api/errors"
import { albumThumbnailUrl, assetThumbnailUrl, personThumbnailUrl } from "../api/games"
import { updateReport } from "../api/reports"
import type { AdminReportOut } from "../api/types/reports"
import { ReportEntity } from "../api/types/reports"
import { Button } from "../games/shared/Button"
import { ImmichLink } from "../games/shared/ImmichLink"
import { PersonAvatar } from "../games/shared/PersonAvatar"
import { reasonLabelKey } from "../games/shared/reportReasons"

const THUMBNAIL_URL: Record<ReportEntity, (id: string) => string> = {
  [ReportEntity.Person]: personThumbnailUrl,
  [ReportEntity.Album]: albumThumbnailUrl,
  [ReportEntity.Asset]: assetThumbnailUrl,
}

interface AdminReportRowProps {
  report: AdminReportOut
  // Replaces this row's entry in the parent's list on a successful resolve/revert, instead of
  // refetching the whole page for one row's change (see AdminReportsList.tsx).
  onResolved: (updated: AdminReportOut) => void
}

// One row per report in AdminReportsList.tsx's list - mirrors AdminInviteRow.tsx's shape
// (state/note on the left, action on the right, local busy/error).
export function AdminReportRow({ report, onResolved }: AdminReportRowProps) {
  const { t, i18n } = useTranslation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleToggle() {
    setBusy(true)
    setError(null)
    try {
      onResolved(await updateReport(report.id, !report.solved))
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
      setBusy(false)
    }
  }

  return (
    <div className="mt-2 flex items-start gap-3 rounded-xl border border-line-soft px-4 py-3">
      <PersonAvatar src={THUMBNAIL_URL[report.entity_type](report.entity_id)} alt="" />
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold text-ink">
          {report.entity_name ?? t("admin.reports.deletedEntity")}
        </p>
        <p className="text-sm text-body">{t(reasonLabelKey(report.reason))}</p>
        {report.note && <p className="mt-1 text-sm text-muted">"{report.note}"</p>}
        <p className="mt-1 text-xs text-faint">
          {t("admin.reports.reportedBy", {
            username: report.username,
            date: new Date(report.created_at).toLocaleDateString(i18n.language),
          })}
        </p>
        {error && <p className="mt-1 text-xs font-semibold text-rose-600">{error}</p>}
        <div className="mt-2 flex items-center gap-3">
          <ImmichLink kind={report.entity_type} id={report.entity_id} />
          <Button
            variant="secondary"
            className="px-4 py-2 text-sm"
            onClick={handleToggle}
            disabled={busy}
          >
            {report.solved ? t("admin.reports.markUnsolved") : t("admin.reports.markSolved")}
          </Button>
        </div>
      </div>
    </div>
  )
}
