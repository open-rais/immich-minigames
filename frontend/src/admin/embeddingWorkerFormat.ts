import type { TFunction } from "i18next"

import type { EmbeddingCoverageOut, EmbeddingJobOut } from "../api/types/admin"

// Pure formatting/decision logic for AdminWorkersSection.tsx, kept here (no React, no fetch) so
// it's testable without jsdom - same split as games/shared/dailyShareText.ts.

export function coverageLabel(t: TFunction, coverage: EmbeddingCoverageOut): string {
  return t("admin.workers.coverage", { cached: coverage.cached, total: coverage.total })
}

// A job with total: 0 (nothing was stale/eligible when it started) is complete the instant it
// starts - without this branch, 0/0 would divide to NaN instead of reading as a full bar.
export function jobProgressPercent(job: EmbeddingJobOut): number {
  if (job.total === 0) return 100
  return Math.min(100, Math.round((job.processed / job.total) * 100))
}

export function jobProgressLabel(t: TFunction, job: EmbeddingJobOut): string {
  return job.failed > 0
    ? t("admin.workers.progressWithFailed", {
        processed: job.processed,
        total: job.total,
        failed: job.failed,
      })
    : t("admin.workers.progress", { processed: job.processed, total: job.total })
}

// The backend only ever runs one job at a time (services/embedding_jobs.py) - a second start
// while one is running 409s. All four buttons disable together while any job is running,
// regardless of which entity it's for, so the UI never invites that 409 in the first place.
export function isJobRunning(job: EmbeddingJobOut | null): job is EmbeddingJobOut {
  return job !== null && job.status === "running"
}
