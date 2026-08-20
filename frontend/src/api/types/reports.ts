// Mirrors backend/src/games/report_spec.py and backend/src/api/dto/reports.py's CreateReportIn.

export const ReportEntity = {
  Asset: "asset",
  Person: "person",
  Album: "album",
} as const
export type ReportEntity = (typeof ReportEntity)[keyof typeof ReportEntity]

export const ReportReason = {
  PersonBirthDate: "person_birth_date",
  PersonNameFaceMismatch: "person_name_face_mismatch",
  PersonNameSpelling: "person_name_spelling",
  AlbumCoverMismatch: "album_cover_mismatch",
  AlbumNameSpelling: "album_name_spelling",
  AssetLocation: "asset_location",
  AssetDate: "asset_date",
  AssetFaceMismatch: "asset_face_mismatch",
} as const
export type ReportReason = (typeof ReportReason)[keyof typeof ReportReason]

export interface CreateReportIn {
  entity_type: ReportEntity
  entity_id: string
  reasons: ReportReason[]
  note: string | null
}

// Mirrors backend/src/api/dto/reports.py's ReportContextOut - sparse, only the fields that apply
// to the entity_type the caller asked about are set.
export interface ReportContextOut {
  name: string | null
  birth_date: string | null
  latitude: number | null
  longitude: number | null
  city: string | null
  country: string | null
  start_date: string | null
  end_date: string | null
  persons: string[] | null
}

// Mirrors backend/src/api/dto/reports.py's AdminReportOut/AdminReportCountsOut.
export interface AdminReportOut {
  id: string
  entity_type: ReportEntity
  entity_id: string
  // None when the entity no longer exists in Immich (deleted since the report was filed).
  entity_name: string | null
  reason: ReportReason
  note: string | null
  user_id: string
  username: string
  solved: boolean
  solved_at: string | null
  created_at: string
}

export interface AdminReportCountsOut {
  asset: number
  person: number
  album: number
}
