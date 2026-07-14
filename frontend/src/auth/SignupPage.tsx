import { useState } from "react"
import type { FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { Link, Navigate, useNavigate } from "react-router-dom"

import { apiErrorMessage } from "../api/errors"
import { Button } from "../games/shared/Button"
import { AuthCard } from "./AuthCard"
import { AuthField } from "./AuthField"
import { useAuth } from "./useAuth"

export function SignupPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user, loading, register } = useAuth()
  const [email, setEmail] = useState("")
  const [username, setUsername] = useState("")
  const [fullName, setFullName] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!loading && user) return <Navigate to="/profile" replace />

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await register({ email, username, full_name: fullName, password })
      navigate("/profile")
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard
      title={t("auth.signup.title")}
      backLabel={t("common.back")}
      onBack={() => navigate("/")}
      footer={
        <>
          {t("auth.signup.hasAccount")}{" "}
          <Link to="/login" className="font-semibold text-primary hover:text-primary-hover">
            {t("auth.login.cta")}
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <AuthField
          id="fullName"
          type="text"
          label={t("auth.fields.fullName")}
          autoComplete="name"
          required
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
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
          onChange={(e) => setUsername(e.target.value)}
        />
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
          autoComplete="new-password"
          minLength={8}
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="text-sm font-semibold text-rose-600">{error}</p>}
        <Button type="submit" variant="primary" className="mt-2 w-full py-2.5" disabled={busy}>
          {t("auth.signup.cta")}
        </Button>
      </form>
    </AuthCard>
  )
}
