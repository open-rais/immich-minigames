import { useMemo, useState } from "react"
import type { FormEvent } from "react"
import { useTranslation } from "react-i18next"

import { updateUser, updateUserSkin } from "../api/admin"
import { apiErrorMessage } from "../api/errors"
import { personThumbnailUrl } from "../api/games"
import type { User } from "../api/types"
import { AuthField } from "../auth/AuthField"
import { Button } from "../games/shared/Button"
import { PersonAvatar } from "../games/shared/PersonAvatar"
import { PersonSearchInput } from "../games/shared/PersonSearchInput"
import { SettingAccordion } from "./SettingAccordion"

interface AdminUserRowProps {
  user: User
  // Replaces this row's entry in the parent's list on a successful save, instead of refetching
  // every user for a single row's edit (see AdminUsersSection.tsx).
  onUpdated: (updated: User) => void
}

// Admin feature (ADMIN-FEATURE.md point #3) - editing (full name/username/skin) for an arbitrary
// account, mirroring auth/EditProfilePage.tsx + auth/SkinPicker.tsx's fields and flow but against
// api/admin.ts instead of the self-service api/auth.ts, and operating on the `user` prop instead
// of useAuth()'s own account.
export function AdminUserRow({ user, onUpdated }: AdminUserRowProps) {
  const { t } = useTranslation()
  const [username, setUsername] = useState(user.username)
  const [fullName, setFullName] = useState(user.full_name)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

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

  return (
    <SettingAccordion nested title={user.full_name} description={user.email}>
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
          pattern="^[a-zA-Z0-9_-]+$"
          required
          value={username}
          onChange={(e) => {
            setUsername(e.target.value)
            setSaved(false)
          }}
        />
        <Button type="submit" variant="primary" className="w-full py-2.5" disabled={busy}>
          {t("auth.profile.save")}
        </Button>
      </form>

      <div className="my-6 border-t border-line" />

      <div className="flex flex-col gap-3">
        <p className="text-sm font-semibold text-muted">{t("auth.profile.skin.label")}</p>
        <div className="flex items-center gap-3">
          {user.skin_person_id ? (
            <PersonAvatar src={personThumbnailUrl(user.skin_person_id)} alt="" />
          ) : (
            <div className="flex h-10 w-10 flex-none items-center justify-center rounded-full border border-dashed border-line-strong text-xs text-faint md:h-14 md:w-14">
              {t("auth.profile.skin.none")}
            </div>
          )}
          {user.skin_person_id && (
            <Button variant="secondary" className="px-4 py-2 text-sm" onClick={() => applySkin(null)} disabled={busy}>
              {t("auth.profile.skin.clear")}
            </Button>
          )}
        </div>
        <PersonSearchInput excludeIds={excludeIds} onSelect={applySkin} disabled={busy} />
      </div>

      {error && <p className="mt-4 text-sm font-semibold text-rose-600">{error}</p>}
      {saved && !error && <p className="mt-4 text-sm font-semibold text-emerald-600">{t("auth.profile.saved")}</p>}
    </SettingAccordion>
  )
}
