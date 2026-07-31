import { useState } from "react"
import type { FormEvent } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate, useSearchParams } from "react-router-dom"

import { resetPassword } from "../api/auth"
import { apiErrorMessage } from "../api/errors"
import { Button } from "../games/shared/Button"
import { AuthCard } from "./AuthCard"
import { AuthField } from "./AuthField"

// Public page (unlike ChangePasswordPage.tsx, no auth guard: the whole point is
// a locked-out user with no session) reached via the admin-generated /reset-password?token=...
// link (see admin/AdminUserRow.tsx). Token pre-fills from the query param, same pattern
// SignupPage.tsx already uses for its own ?invite= param - still editable, so a token shared
// out-of-band from the link itself can be pasted in directly too.
export function ResetPasswordPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [token, setToken] = useState(searchParams.get("token") ?? "")
  const [newPassword, setNewPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await resetPassword({ token, new_password: newPassword })
      // No auto-login (the backend never issues a cookie here) - straight to the login form with
      // the new password.
      navigate("/login", { replace: true })
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard
      title={t("auth.resetPassword.title")}
      backLabel={t("common.back")}
      onBack={() => navigate("/login")}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <AuthField
          id="token"
          type="text"
          label={t("auth.resetPassword.token")}
          required
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        <AuthField
          id="newPassword"
          type="password"
          label={t("auth.resetPassword.newPassword")}
          autoComplete="new-password"
          minLength={8}
          maxLength={128}
          required
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />
        {error && <p className="text-sm font-semibold text-rose-600">{error}</p>}
        <Button type="submit" variant="primary" className="mt-2 w-full py-2.5" disabled={busy}>
          {t("auth.resetPassword.submit")}
        </Button>
      </form>
    </AuthCard>
  )
}
