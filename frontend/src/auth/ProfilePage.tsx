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

// Edit form (roadmap point E - was read-only "lo básico" per point B) - username/full name
// editable, email and member-since stay read-only, plus the cosmetic skin picker (SkinPicker.tsx).
export function ProfilePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user, loading, logout, updateProfile } = useAuth()
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

  async function handleLogout() {
    setBusy(true)
    try {
      await logout()
      navigate("/")
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title={t("auth.profile.title")} backLabel={t("common.back")} onBack={() => navigate("/")}>
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
        <div>
          <p className="text-sm font-semibold text-muted">{t("auth.fields.email")}</p>
          <p className="text-[15px] text-ink">{user.email}</p>
        </div>
        {error && <p className="text-sm font-semibold text-rose-600">{error}</p>}
        {saved && !error && <p className="text-sm font-semibold text-emerald-600">{t("auth.profile.saved")}</p>}
        <Button type="submit" variant="primary" className="w-full py-2.5" disabled={busy}>
          {t("auth.profile.save")}
        </Button>
      </form>

      <div className="my-6 border-t border-line" />
      <SkinPicker />

      <p className="mt-6 text-center text-sm text-faint">
        {t("auth.profile.memberSince", { date: new Date(user.created_at).toLocaleDateString() })}
      </p>

      <Button variant="secondary" className="mt-6 w-full py-2.5" onClick={handleLogout} disabled={busy}>
        {t("auth.profile.logout")}
      </Button>
    </AuthCard>
  )
}
