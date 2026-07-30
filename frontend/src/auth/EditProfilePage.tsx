import { useEffect, useMemo, useState } from "react"
import type { FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { apiErrorMessage } from "../api/errors"
import { Button } from "../games/shared/Button"
import { PersonSearchInput } from "../games/shared/PersonSearchInput"
import { AuthCard } from "./AuthCard"
import { AuthField } from "./AuthField"
import { ProfileAvatar, ProfileAvatarPlaceholder } from "./ProfileAvatar"
import { useAuth } from "./useAuth"

// Edit form (roadmap point E) - reached from ProfilePage's "Edit profile" button, separate from
// the read-only profile view so that page can stay a plain "here's your account" display.
// Editable username/full name, plus the cosmetic skin (avatar) picker; email stays read-only (no
// endpoint to change it - would need re-verification this app doesn't have yet).
export function EditProfilePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user, updateProfile, updateSkin } = useAuth()
  const [username, setUsername] = useState("")
  const [fullName, setFullName] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const excludeIds = useMemo(
    () => (user?.skin_person_id ? new Set([user.skin_person_id]) : new Set<string>()),
    [user?.skin_person_id],
  )

  // Synced from `user` rather than a plain useState(user?.username) initializer - user arrives
  // asynchronously (AuthProvider's getMe() on mount), so the very first render (before loading
  // finishes) would otherwise permanently lock these fields to "".
  useEffect(() => {
    if (user) {
      setUsername(user.username)
      setFullName(user.full_name)
    }
  }, [user])

  // Roadmap #H, F3 - RequireAuth (App.tsx) already guarantees a session before this page ever
  // mounts; this is just a TypeScript narrowing helper (user: User | null), not reachable at
  // runtime.
  if (!user) return null

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      await updateProfile({ username, full_name: fullName })
      setSaved(true)
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  // Applies immediately on selection/removal, same as before this screen's layout changed - not
  // tied to the "Guardar" button below, which only ever covers full name/username.
  async function applySkin(personId: string | null) {
    setBusy(true)
    setError(null)
    try {
      await updateSkin(personId)
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title={t("auth.profile.edit")} backLabel={t("common.back")} onBack={() => navigate("/profile")}>
      <div className="mb-6 flex items-center justify-center gap-3">
        {user.skin_person_id ? (
          <ProfileAvatar key={user.skin_person_id} personId={user.skin_person_id} />
        ) : (
          <ProfileAvatarPlaceholder />
        )}
        {user.skin_person_id && (
          <Button
            type="button"
            variant="secondary"
            className="px-4 py-2.5"
            onClick={() => applySkin(null)}
            disabled={busy}
          >
            {t("auth.profile.skin.clear")}
          </Button>
        )}
      </div>

      <form onSubmit={handleSave} className="flex flex-col gap-4">
        <AuthField
          id="fullName"
          type="text"
          label={t("auth.fields.fullName")}
          autoComplete="name"
          required
          value={fullName}
          onChange={(e) => {
            setFullName(e.target.value)
            setSaved(false)
          }}
        />
        <AuthField
          id="username"
          type="text"
          label={t("auth.fields.username")}
          autoComplete="username"
          minLength={3}
          maxLength={32}
          pattern="^[a-zA-Z0-9_-]+$"
          required
          value={username}
          onChange={(e) => {
            setUsername(e.target.value)
            setSaved(false)
          }}
        />
        <div className="flex flex-col gap-1.5">
          <p className="text-sm font-semibold text-body">{t("auth.fields.person")}</p>
          <PersonSearchInput excludeIds={excludeIds} onSelect={applySkin} disabled={busy} />
        </div>
        {error && <p className="text-sm font-semibold text-rose-600">{error}</p>}
        {saved && !error && <p className="text-sm font-semibold text-emerald-600">{t("auth.profile.saved")}</p>}
        <Button type="submit" variant="primary" className="w-full py-2.5" disabled={busy}>
          {t("auth.profile.save")}
        </Button>
      </form>
    </AuthCard>
  )
}
