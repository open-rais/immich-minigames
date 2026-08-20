import { apiClient } from "./client"
import type { CreateReportIn, ReportContextOut, ReportEntity } from "./types/reports"

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
