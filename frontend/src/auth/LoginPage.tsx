import { useState } from "react"
import type { FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Link, Navigate, useNavigate } from "react-router-dom"

import { apiErrorMessage } from "../api/errors"
import { Button } from "../games/shared/Button"
import { AuthCard } from "./AuthCard"
import { AuthField } from "./AuthField"
import { useAuth } from "./useAuth"

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user, loading, login } = useAuth()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!loading && user) return <Navigate to="/profile" replace />

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login({ email, password })
      navigate("/profile")
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard
      title={t("auth.login.title")}
      backLabel={t("common.back")}
      onBack={() => navigate("/")}
      footer={
        <>
          {t("auth.login.noAccount")}{" "}
          <Link to="/signup" className="font-semibold text-primary hover:text-primary-hover">
            {t("auth.signup.cta")}
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <AuthField
          id="email"
          type="email"
          label={t("auth.fields.email")}
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <AuthField
          id="password"
          type="password"
          label={t("auth.fields.password")}
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="text-sm font-semibold text-rose-600">{error}</p>}
        <Button type="submit" variant="primary" className="mt-2 w-full py-2.5" disabled={busy}>
          {t("auth.login.cta")}
        </Button>
      </form>
    </AuthCard>
  )
}
