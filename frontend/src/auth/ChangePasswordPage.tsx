import { useState } from "react"
import type { FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { apiErrorMessage } from "../api/errors"
import { Button } from "../games/shared/Button"
import { AuthCard } from "./AuthCard"
import { AuthField } from "./AuthField"
import { useAuth } from "./useAuth"

// Roadmap #H, F0 - self-service password change, reached from ProfilePage's "Change password"
// button. Same shell/state shape as EditProfilePage.tsx; kept as its own page (rather than a
// section on EditProfilePage) since it's a distinct action with its own current/new-password
// fields, not a profile field being edited in place.
export function ChangePasswordPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  // Roadmap #H, F3 - no more session guard here at all: RequireAuth (App.tsx) already guarantees
  // one before this page mounts, and unlike ProfilePage/EditProfilePage this page never reads
  // `user` itself, so there's nothing left needing a TypeScript narrowing check either.
  const { changePassword } = useAuth()
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword })
      setCurrentPassword("")
      setNewPassword("")
      setSaved(true)
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard
      title={t("auth.profile.changePassword.title")}
      backLabel={t("common.back")}
      onBack={() => navigate("/profile")}
    >
      <form onSubmit={handleSave} className="flex flex-col gap-4">
        <AuthField
          id="currentPassword"
          type="password"
          label={t("auth.profile.changePassword.currentPassword")}
          autoComplete="current-password"
          required
          value={currentPassword}
          onChange={(e) => {
            setCurrentPassword(e.target.value)
            setSaved(false)
          }}
        />
        <AuthField
          id="newPassword"
          type="password"
          label={t("auth.profile.changePassword.newPassword")}
          autoComplete="new-password"
          minLength={8}
          maxLength={128}
          required
          value={newPassword}
          onChange={(e) => {
            setNewPassword(e.target.value)
            setSaved(false)
          }}
        />
        {error && <p className="text-sm font-semibold text-rose-600">{error}</p>}
        {saved && !error && (
          <p className="text-sm font-semibold text-emerald-600">
            {t("auth.profile.changePassword.saved")}
          </p>
        )}
        <Button type="submit" variant="primary" className="w-full py-2.5" disabled={busy}>
          {t("auth.profile.changePassword.save")}
        </Button>
      </form>
    </AuthCard>
  )
}
