import { useCallback, useEffect, useState } from "react"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"

import { cancelEmbeddingJob, getEmbeddingWorkerStatus, startEmbeddingJob } from "../api/admin"
import { apiErrorMessage } from "../api/errors"
import type { EmbeddingEntity, EmbeddingScope, EmbeddingWorkersStatusOut } from "../api/types/admin"
import { Button } from "../games/shared/Button"
import { coverageLabel, isJobRunning, jobProgressLabel, jobProgressPercent } from "./embeddingWorkerFormat"

function EntityBlock({
  title,
  coverage,
  onProcessMissing,
  onReprocessAll,
  disabled,
  extra,
}: {
  title: string
  coverage: string
  onProcessMissing: () => void
  onReprocessAll: () => void
  disabled: boolean
  extra?: ReactNode
}) {
  const { t } = useTranslation()
  return (
    <div className="rounded-xl border border-line-soft p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-body">{title}</h3>
        <span className="text-sm text-muted">{coverage}</span>
      </div>
      <div className="mt-3 flex gap-3">
        <Button variant="secondary" className="flex-1 py-2" onClick={onProcessMissing} disabled={disabled}>
          {t("admin.workers.processMissing")}
        </Button>
        <Button variant="secondary" className="flex-1 py-2" onClick={onReprocessAll} disabled={disabled}>
          {t("admin.workers.reprocessAll")}
        </Button>
      </div>
      {extra && <div className="mt-3">{extra}</div>}
    </div>
  )
}

// Content of the "Embedding cache" top-level accordion in AdminPage.tsx - two blocks (Personas/
// Álbumes), each with a coverage counter and "Process missing"/"Reprocess all" buttons, plus a
// shared progress bar + cancel button while a job is running (the backend only ever runs one job
// at a time, see services/embedding_jobs.py, so all four buttons disable together rather than
// per-block).
//
// Deliberately doesn't use api/queryCache.ts's useLiveQuery: that cache's whole model is "show
// what's cached, always re-fetch when something asks again" - it has no notion of a recurring
// interval. This panel needs to repoll roughly every second while a job is running to drive its
// progress bar, a different shape of problem, so it's a plain local useEffect + setInterval
// instead - torn down (not just skipped) the moment the job stops running, rather than left
// polling forever in the background.
export function AdminWorkersSection() {
  const { t } = useTranslation()
  const [status, setStatus] = useState<EmbeddingWorkersStatusOut | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [includeIneligible, setIncludeIneligible] = useState(false)
  const [starting, setStarting] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const next = await getEmbeddingWorkerStatus()
      setStatus(next)
      setLoadError(null)
    } catch (err) {
      setLoadError(apiErrorMessage(err) ?? t("auth.error.generic"))
    }
  }, [t])

  useEffect(() => {
    refresh()
  }, [refresh])

  const running = isJobRunning(status?.job ?? null)

  useEffect(() => {
    if (!running) return
    const interval = setInterval(refresh, 1000)
    return () => clearInterval(interval)
  }, [running, refresh])

  async function handleStart(entity: EmbeddingEntity, scope: EmbeddingScope) {
    setStarting(true)
    setActionError(null)
    try {
      const startedJob = await startEmbeddingJob({
        entity,
        scope,
        include_ineligible: entity === "person" ? includeIneligible : false,
      })
      setStatus((prev) => (prev ? { ...prev, job: startedJob } : prev))
    } catch (err) {
      setActionError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setStarting(false)
    }
  }

  async function handleCancel() {
    setCancelling(true)
    setActionError(null)
    try {
      await cancelEmbeddingJob()
      await refresh()
    } catch (err) {
      setActionError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setCancelling(false)
    }
  }

  if (loadError && !status) return <p className="text-sm font-semibold text-rose-600">{loadError}</p>
  if (!status) return <p className="text-sm text-faint">{t("admin.workers.loading")}</p>

  const job = status.job
  const buttonsDisabled = running || starting

  return (
    <div className="flex flex-col gap-5">
      {loadError && <p className="text-sm font-semibold text-rose-600">{loadError}</p>}

      <EntityBlock
        title={t("admin.workers.persons")}
        coverage={coverageLabel(t, status.persons)}
        onProcessMissing={() => handleStart("person", "missing")}
        onReprocessAll={() => handleStart("person", "all")}
        disabled={buttonsDisabled}
        extra={
          <label className="flex items-center gap-2.5 text-sm font-semibold text-body">
            <input
              type="checkbox"
              checked={includeIneligible}
              disabled={buttonsDisabled}
              onChange={(e) => setIncludeIneligible(e.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            {t("admin.workers.includeIneligible")}
          </label>
        }
      />

      <EntityBlock
        title={t("admin.workers.albums")}
        coverage={coverageLabel(t, status.albums)}
        onProcessMissing={() => handleStart("album", "missing")}
        onReprocessAll={() => handleStart("album", "all")}
        disabled={buttonsDisabled}
      />

      {job && running && (
        <div className="rounded-xl border border-line-soft p-4">
          <p className="text-sm font-semibold text-body">
            {t(`admin.workers.entityLabel.${job.entity}`)} — {t(`admin.workers.scopeLabel.${job.scope}`)}
          </p>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-hover-tint">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${jobProgressPercent(job)}%` }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between">
            <span className="text-sm text-muted">{jobProgressLabel(t, job)}</span>
            <Button
              variant="secondary"
              className="px-4 py-1.5 text-sm"
              onClick={handleCancel}
              disabled={cancelling}
            >
              {t("admin.workers.cancel")}
            </Button>
          </div>
        </div>
      )}

      {job && job.status === "failed" && job.error && (
        <p className="text-sm font-semibold text-rose-600">{t("admin.workers.failed", { error: job.error })}</p>
      )}

      {actionError && <p className="text-sm font-semibold text-rose-600">{actionError}</p>}
    </div>
  )
}
