import { useState } from "react"
import { Navigate, useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { personThumbnailUrl } from "../api/games"
import { Button } from "../games/shared/Button"
import { AuthCard } from "./AuthCard"
import { useAuth } from "./useAuth"

// Same img+onError fallback convention as menu/UserMenu.tsx's SkinAvatar / games/shared/
// PersonAvatar.tsx, just sized as a page hero avatar instead of a small circle. Rendered with
// `key={personId}` by the caller so switching skins resets `failed` instead of keeping a stale
// placeholder around.
function ProfileAvatar({ personId }: { personId: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return <ProfileAvatarPlaceholder />
  return (
    <img
      src={personThumbnailUrl(personId)}
      alt=""
      onError={() => setFailed(true)}
      className="h-24 w-24 rounded-full object-cover shadow-card"
    />
  )
}

function ProfileAvatarPlaceholder() {
  return <div className="h-24 w-24 rounded-full border border-dashed border-line-strong" />
}

// Read-only account view (roadmap point B's "lo básico", plus the skin avatar from roadmap point
// E) - actual editing (username/full name/skin) lives on its own page, reached via "Edit profile"
// (see EditProfilePage.tsx), so this one stays a plain "here's your account" display.
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
    <AuthCard title={t("auth.profile.title")} backLabel={t("common.back")} onBack={() => navigate("/")}>
      <div className="mb-6 flex justify-center">
        {user.skin_person_id ? (
          <ProfileAvatar key={user.skin_person_id} personId={user.skin_person_id} />
        ) : (
          <ProfileAvatarPlaceholder />
        )}
      </div>

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

      <Button variant="primary" className="mt-6 w-full py-2.5" onClick={() => navigate("/profile/edit")}>
        {t("auth.profile.edit")}
      </Button>
      <Button variant="secondary" className="mt-3 w-full py-2.5" onClick={handleLogout} disabled={busy}>
        {t("auth.profile.logout")}
      </Button>
    </AuthCard>
  )
}
