// Admin-editable game/daily settings and invites - mirrors backend/src/api/dto/admin.py.

// `key` names match services/game_settings.py's
// SettingSpec keys (e.g. "decay_km", "total_rounds") - see admin/AdminGameRow.tsx for how they're
// labeled.
export interface GameSettingOut {
  key: string
  value: number
  default: number
  value_type: "int" | "float"
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
