import { useEffect, useState } from "react"
import type { FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Navigate, useNavigate } from "react-router-dom"

import { apiErrorMessage } from "../api/errors"
import { Button } from "../games/shared/Button"
import { AuthCard } from "./AuthCard"
import { AuthField } from "./AuthField"
import { SkinPicker } from "./SkinPicker"
import { useAuth } from "./useAuth"

// Edit form (roadmap point E) - reached from ProfilePage's "Edit profile" button, separate from
// the read-only profile view so that page can stay a plain "here's your account" display. Editable
// username/full name, plus the cosmetic skin picker (SkinPicker.tsx); email stays read-only (no
// endpoint to change it - would need re-verification this app doesn't have yet).
export function EditProfilePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user, loading, updateProfile } = useAuth()
  const [username, setUsername] = useState("")
  const [fullName, setFullName] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  // Synced from `user` rather than a plain useState(user?.username) initializer - user arrives
  // asynchronously (AuthProvider's getMe() on mount), so the very first render (before loading
  // finishes) would otherwise permanently lock these fields to "".
  useEffect(() => {
    if (user) {
      setUsername(user.username)
      setFullName(user.full_name)
    }
  }, [user])

  if (!loading && !user) return <Navigate to="/login" replace />
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

  return (
    <AuthCard title={t("auth.profile.edit")} backLabel={t("common.back")} onBack={() => navigate("/profile")}>
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
        {error && <p className="text-sm font-semibold text-rose-600">{error}</p>}
        {saved && !error && <p className="text-sm font-semibold text-emerald-600">{t("auth.profile.saved")}</p>}
        <Button type="submit" variant="primary" className="w-full py-2.5" disabled={busy}>
          {t("auth.profile.save")}
        </Button>
      </form>

      <div className="my-6 border-t border-line" />
      <SkinPicker />
    </AuthCard>
  )
}
