import { apiClient } from "./client"
import type {
  AdminReportCountsOut,
  AdminReportOut,
  CreateReportIn,
  ReportContextOut,
  ReportEntity,
} from "./types/reports"

// backend/src/api/reports_api.py's create_report - 201 with no response body.
export async function createReport(body: CreateReportIn): Promise<void> {
  await apiClient.post("/reports", body)
}

// backend/src/api/reports_api.py's get_report_context - null when the entity no longer exists in
// Immich, same non-blocking stance the rest of this feature already has.
export async function getReportContext(
  entityType: ReportEntity,
  entityId: string,
): Promise<ReportContextOut | null> {
  const { data } = await apiClient.get<ReportContextOut | null>("/reports/context", {
    params: { entity_type: entityType, entity_id: entityId },
  })
  return data
}

// backend/src/api/admin_reports_api.py. Paginated (roadmap infinite-scroll UI, see
// admin/useInfiniteAdminList.ts) - same offset/limit convention as api/admin.ts's listInvites.
export async function listReports(
  entityType: ReportEntity,
  solved: boolean,
  opts?: { offset?: number; limit?: number },
): Promise<AdminReportOut[]> {
  const { data } = await apiClient.get<AdminReportOut[]>("/admin/reports", {
    params: { entity_type: entityType, solved, offset: opts?.offset, limit: opts?.limit },
  })
  return data
}

export async function getReportCounts(): Promise<AdminReportCountsOut> {
  const { data } = await apiClient.get<AdminReportCountsOut>("/admin/reports/counts")
  return data
}

export async function updateReport(reportId: string, solved: boolean): Promise<AdminReportOut> {
  const { data } = await apiClient.patch<AdminReportOut>(`/admin/reports/${reportId}`, { solved })
  return data
}
