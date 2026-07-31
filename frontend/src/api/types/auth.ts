// Mirrors backend/src/api/auth_schemas.py - own accounts, unrelated to Immich's own users.

export interface User {
  id: string
  email: string
  username: string
  full_name: string
  // Cosmetic avatar - an Immich Person id, or null if none picked yet. Shown in the header's user
  // circle (see menu/UserMenu.tsx) via personThumbnailUrl.
  skin_person_id: string | null
  // Promoted server-side via ADMIN_EMAIL, never set from the frontend. Gates the admin panel link
  // (menu/UserMenu.tsx) and the /admin routes (admin/AdminLayout.tsx).
  is_admin: boolean
  created_at: string
}

export interface RegisterIn {
  email: string
  username: string
  full_name: string
  password: string
  // Required except for the very first account (see backend/src/services/
  // auth_service.py's _authorize_registration bootstrap check).
  invite_code?: string
}

export interface LoginIn {
  email: string
  password: string
}

// PATCH semantics - omit a field (or send undefined) to leave it unchanged, mirrors
// backend/src/api/auth_schemas.py's UpdateProfileIn.
export interface UpdateProfileIn {
  username?: string
  full_name?: string
}

// Mirrors backend/src/api/auth_schemas.py's ChangePasswordIn.
export interface ChangePasswordIn {
  current_password: string
  new_password: string
}

// Mirrors backend/src/api/auth_schemas.py's ResetPasswordIn.
export interface ResetPasswordIn {
  token: string
  new_password: string
}
