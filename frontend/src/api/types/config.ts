// Roadmap point #10 (rounds review) - mirrors backend/src/api/dto/config.py.

export interface ConfigOut {
  immich_external_url: string | null
  // null when Web Push isn't configured (backend VAPID_* unset) - the frontend hides the whole
  // notifications section of settings in that case.
  push_public_key: string | null
}
