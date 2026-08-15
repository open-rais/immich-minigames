// Admin-editable game/daily settings and invites - mirrors backend/src/api/dto/admin.py.

// `key` names match services/game_settings.py's
// SettingSpec keys (e.g. "decay_km", "total_rounds") - see admin/AdminGameRow.tsx for how they're
// labeled.
export interface GameSettingOut {
  key: string
  value: number
  default: number
  value_type: "int" | "float" | "bool"
  min_value: number
  max_value: number
}

export interface GameSettingsOut {
  game_type: string
  mode: string
  settings: GameSettingOut[]
}

export interface DailySettingsOut {
  game_type: string
  mode: string
  // The "Activar juego diario" checkbox.
  enabled: boolean
  settings: GameSettingOut[]
}

export interface UpdateDailySettingsIn {
  enabled?: boolean
  values?: Record<string, number>
}

export type InviteStatus = "pending" | "used" | "expired"

export interface InviteOut {
  id: string
  kind: string
  status: InviteStatus
  expires_at: string
  used_at: string | null
  created_at: string
}

export interface CreateInviteOut {
  id: string
  // The only time the plain token is ever available - shown once via ShareModal, see
  // admin/AdminInvitesSection.tsx.
  token: string
  expires_at: string
}

// Embedding cache worker (backend/src/api/admin_workers_api.py) - recomputes Persondle's
// face-similarity cache and Albumdle's similarity cache in the background.

export type EmbeddingEntity = "person" | "album"
export type EmbeddingScope = "missing" | "all"
export type EmbeddingJobStatus = "running" | "done" | "cancelled" | "failed"

export interface EmbeddingCoverageOut {
  cached: number
  total: number
}

export interface EmbeddingJobOut {
  id: string
  entity: EmbeddingEntity
  scope: EmbeddingScope
  include_ineligible: boolean
  status: EmbeddingJobStatus
  total: number
  processed: number
  failed: number
  started_at: string
  finished_at: string | null
  error: string | null
}

export interface EmbeddingWorkersStatusOut {
  persons: EmbeddingCoverageOut
  albums: EmbeddingCoverageOut
  // The running job, or the last finished one, or null if nothing has ever run this process.
  job: EmbeddingJobOut | null
}

export interface StartEmbeddingJobIn {
  entity: EmbeddingEntity
  scope: EmbeddingScope
  include_ineligible?: boolean
}
