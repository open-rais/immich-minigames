import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Navigate, useNavigate } from "react-router-dom"

import { BackButton } from "../games/shared/BackButton"
import { Button } from "../games/shared/Button"
import { useAuth } from "./useAuth"

// "Lo básico" per roadmap point B: account info + logout, nothing game-related yet - stats/
// records/played-games summary are roadmap point F ("features de usuarios loggeados"), which
// needs Game.owner wired to real accounts first (deliberately not done by this point).
export function ProfilePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user, loading, logout } = useAuth()
  const [busy, setBusy] = useState(false)

  if (!loading && !user) return <Navigate to="/login" replace />
  if (!user) return null

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
    <div className="flex min-h-screen flex-col items-center justify-center bg-app-bg px-6 py-10">
      <BackButton label={t("common.back")} onClick={() => navigate("/")} />
      <div className="w-full max-w-sm rounded-3xl border border-line bg-surface p-8 shadow-card">
        <h1 className="mb-6 text-center text-2xl font-bold text-ink">{t("auth.profile.title")}</h1>

        <dl className="flex flex-col gap-4">
          <div>
            <dt className="text-sm font-semibold text-muted">{t("auth.fields.fullName")}</dt>
            <dd className="text-[15px] text-ink">{user.full_name}</dd>
          </div>
          <div>
            <dt className="text-sm font-semibold text-muted">{t("auth.fields.username")}</dt>
            <dd className="text-[15px] text-ink">{user.username}</dd>
          </div>
          <div>
            <dt className="text-sm font-semibold text-muted">{t("auth.fields.email")}</dt>
            <dd className="text-[15px] text-ink">{user.email}</dd>
          </div>
        </dl>

        <p className="mt-6 text-center text-sm text-faint">
          {t("auth.profile.memberSince", { date: new Date(user.created_at).toLocaleDateString() })}
        </p>

        <Button variant="secondary" className="mt-6 w-full py-2.5" onClick={handleLogout} disabled={busy}>
          {t("auth.profile.logout")}
        </Button>
      </div>
    </div>
  )
}
