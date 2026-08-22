import { ReportEntity, ReportReason } from "../../api/types/reports"

// Espejado a mano desde backend/src/games/report_spec.py::REASON_ENTITY, invertido - el modal
// necesita "qué razones muestro para este tipo de entidad", no "a qué entidad aplica esta razón".
export const REASONS_FOR_KIND: Record<ReportEntity, ReportReason[]> = {
  [ReportEntity.Person]: [
    ReportReason.PersonBirthDate,
    ReportReason.PersonNameFaceMismatch,
    ReportReason.PersonNameSpelling,
  ],
  [ReportEntity.Album]: [ReportReason.AlbumCoverMismatch, ReportReason.AlbumNameSpelling],
  [ReportEntity.Asset]: [ReportReason.AssetLocation, ReportReason.AssetDate, ReportReason.AssetFaceMismatch],
}

export function reasonLabelKey(reason: ReportReason): string {
  return `reports.reasons.${reason}`
}
