import type { TFunction } from "i18next"
import { describe, expect, it } from "vitest"

import type { EmbeddingJobOut } from "../api/types/admin"
import { coverageLabel, isJobRunning, jobProgressLabel, jobProgressPercent } from "./embeddingWorkerFormat"

// Same stub convention as games/shared/dailyShareText.test.ts: asserts the key and interpolated
// values, not the translated copy, so this doesn't break when the .json locale files are edited.
const t = ((key: string, opts?: Record<string, unknown>) =>
  `${key}:${JSON.stringify(opts)}`) as unknown as TFunction

function job(overrides: Partial<EmbeddingJobOut> = {}): EmbeddingJobOut {
  return {
    id: "job-1",
    entity: "person",
    scope: "missing",
    include_ineligible: false,
    status: "running",
    total: 10,
    processed: 0,
    failed: 0,
    started_at: "2026-08-15T00:00:00Z",
    finished_at: null,
    error: null,
    ...overrides,
  }
}

describe("coverageLabel", () => {
  it("interpolates cached and total into the coverage key", () => {
    expect(coverageLabel(t, { cached: 42, total: 64 })).toBe(
      'admin.workers.coverage:{"cached":42,"total":64}',
    )
  })
})

describe("jobProgressPercent", () => {
  it("is 0 at the start of a run", () => {
    expect(jobProgressPercent(job({ processed: 0, total: 10 }))).toBe(0)
  })

  it("rounds to the nearest percent partway through", () => {
    expect(jobProgressPercent(job({ processed: 1, total: 3 }))).toBe(33)
  })

  it("is 100 once every entity is processed", () => {
    expect(jobProgressPercent(job({ processed: 10, total: 10 }))).toBe(100)
  })

  it("is 100 for a total of 0, instead of dividing by zero into NaN", () => {
    expect(jobProgressPercent(job({ processed: 0, total: 0 }))).toBe(100)
  })

  it("clamps at 100 even if processed somehow exceeds total", () => {
    expect(jobProgressPercent(job({ processed: 11, total: 10 }))).toBe(100)
  })
})

describe("jobProgressLabel", () => {
  it("uses the plain progress key when nothing failed", () => {
    expect(jobProgressLabel(t, job({ processed: 5, total: 10, failed: 0 }))).toBe(
      'admin.workers.progress:{"processed":5,"total":10}',
    )
  })

  it("switches to the with-failed key once at least one entity failed", () => {
    expect(jobProgressLabel(t, job({ processed: 5, total: 10, failed: 2 }))).toBe(
      'admin.workers.progressWithFailed:{"processed":5,"total":10,"failed":2}',
    )
  })
})

describe("isJobRunning", () => {
  it("is false when there is no job at all", () => {
    expect(isJobRunning(null)).toBe(false)
  })

  it("is true only while status is running", () => {
    expect(isJobRunning(job({ status: "running" }))).toBe(true)
  })

  it.each(["done", "cancelled", "failed"] as const)("is false once status is %s", (status) => {
    expect(isJobRunning(job({ status }))).toBe(false)
  })
})
