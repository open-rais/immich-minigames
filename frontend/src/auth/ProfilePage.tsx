import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { Button } from "../games/shared/Button"
import { AuthCard } from "./AuthCard"
import { ProfileAvatar, ProfileAvatarPlaceholder } from "./ProfileAvatar"
import { RecentGamesModal } from "./RecentGamesModal"
import { useAuth } from "./useAuth"

// Read-only account view - actual editing (username/full name/skin) lives on its own page,
// reached via "Edit profile" (see EditProfilePage.tsx), so this one stays a plain "here's your
// account" display.
export function ProfilePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [busy, setBusy] = useState(false)
  const [showRecentGames, setShowRecentGames] = useState(false)

  // RequireAuth (App.tsx) already guarantees a session before this page ever
  // mounts; this is just a TypeScript narrowing helper (user: User | null), not reachable at
  // runtime.
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
    <AuthCard
      title={t("auth.profile.title")}
      backLabel={t("common.back")}
      onBack={() => navigate("/")}
    >
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

      <Button
        variant="primary"
        className="mt-6 w-full py-2.5"
        onClick={() => navigate("/profile/edit")}
      >
        {t("auth.profile.edit")}
      </Button>
      <Button
        variant="secondary"
        className="mt-3 w-full py-2.5"
        onClick={() => navigate("/profile/password")}
      >
        {t("auth.profile.changePassword.title")}
      </Button>
      <Button
        variant="secondary"
        className="mt-3 w-full py-2.5"
        onClick={() => setShowRecentGames(true)}
      >
        {t("auth.profile.viewGames")}
      </Button>
      <Button
        variant="secondary"
        className="mt-3 w-full py-2.5"
        onClick={handleLogout}
        disabled={busy}
      >
        {t("auth.profile.logout")}
      </Button>

      {showRecentGames && <RecentGamesModal onClose={() => setShowRecentGames(false)} />}
    </AuthCard>
  )
}
