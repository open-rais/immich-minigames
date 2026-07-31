import { useMemo, useState } from "react"
import type { FormEvent } from "react"
import { useTranslation } from "react-i18next"

import { createPasswordReset, updateUser, updateUserSkin } from "../api/admin"
import { apiErrorMessage } from "../api/errors"
import { personThumbnailUrl } from "../api/games"
import type { User } from "../api/types/auth"
import { AuthField } from "../auth/AuthField"
import { Button } from "../games/shared/Button"
import { PersonAvatar } from "../games/shared/PersonAvatar"
import { PersonSearchInput } from "../games/shared/PersonSearchInput"
import { ShareModal } from "../games/shared/ShareModal"
import { SettingAccordion } from "./SettingAccordion"

interface AdminUserRowProps {
  user: User
  // Replaces this row's entry in the parent's list on a successful save, instead of refetching
  // every user for a single row's edit (see AdminUsersSection.tsx).
  onUpdated: (updated: User) => void
}

// Editing (full name/username/skin) for an arbitrary
// account, mirroring auth/EditProfilePage.tsx's fields and flow but against api/admin.ts instead
// of the self-service api/auth.ts, and operating on the `user` prop instead of useAuth()'s own
// account. The row's own skin doubles as the accordion header's icon (left of the user's name),
// instead of a second avatar repeated inside the body.
export function AdminUserRow({ user, onUpdated }: AdminUserRowProps) {
  const { t } = useTranslation()
  const [username, setUsername] = useState(user.username)
  const [fullName, setFullName] = useState(user.full_name)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [resetLink, setResetLink] = useState<string | null>(null)

  const excludeIds = useMemo(
    () => (user.skin_person_id ? new Set([user.skin_person_id]) : new Set<string>()),
    [user.skin_person_id],
  )

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const updated = await updateUser(user.id, { username, full_name: fullName })
      onUpdated(updated)
      setSaved(true)
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  async function applySkin(personId: string | null) {
    setBusy(true)
    setError(null)
    try {
      onUpdated(await updateUserSkin(user.id, personId))
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  async function handleResetPassword() {
    setBusy(true)
    setError(null)
    try {
      const created = await createPasswordReset(user.id)
      setResetLink(`${window.location.origin}/reset-password?token=${created.token}`)
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  return (
    <SettingAccordion
      nested
      icon={
        <PersonAvatar
          src={user.skin_person_id ? personThumbnailUrl(user.skin_person_id) : null}
          alt=""
        />
      }
      title={user.full_name}
      description={user.email}
    >
      <form onSubmit={handleSave} className="flex flex-col gap-4">
        <AuthField
          id={`fullName-${user.id}`}
          type="text"
          label={t("auth.fields.fullName")}
          required
          value={fullName}
          onChange={(e) => {
            setFullName(e.target.value)
            setSaved(false)
          }}
        />
        <AuthField
          id={`username-${user.id}`}
          type="text"
          label={t("auth.fields.username")}
          minLength={3}
          maxLength={32}
          pattern="^[a-zA-Z0-9_\-]+$"
          required
          value={username}
          onChange={(e) => {
            setUsername(e.target.value)
            setSaved(false)
          }}
        />
        <div className="flex flex-col gap-1.5">
          <p className="text-sm font-semibold text-body">{t("auth.fields.person")}</p>
          <div className="flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <PersonSearchInput excludeIds={excludeIds} onSelect={applySkin} disabled={busy} />
            </div>
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
        </div>
        {error && <p className="text-sm font-semibold text-rose-600">{error}</p>}
        {saved && !error && (
          <p className="text-sm font-semibold text-emerald-600">{t("auth.profile.saved")}</p>
        )}
        <Button type="submit" variant="primary" className="w-full py-2.5" disabled={busy}>
          {t("auth.profile.save")}
        </Button>
      </form>

      <Button
        variant="secondary"
        className="mt-3 w-full py-2.5"
        onClick={handleResetPassword}
        disabled={busy}
      >
        {t("auth.profile.resetPassword")}
      </Button>

      {resetLink && <ShareModal text={resetLink} onClose={() => setResetLink(null)} />}
    </SettingAccordion>
  )
}
