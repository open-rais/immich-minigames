import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { listUsers } from "../api/admin"
import { apiErrorMessage } from "../api/errors"
import type { User } from "../api/types"
import { AdminUserRow } from "./AdminUserRow"

// Admin feature (ADMIN-FEATURE.md point #3) - content of the "Usuarios" top-level accordion in
// AdminPage.tsx. Mounts lazily (SettingAccordion only mounts children on first expand), so the
// list isn't fetched until the admin actually opens this section.
export function AdminUsersSection() {
  const { t } = useTranslation()
  const [users, setUsers] = useState<User[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listUsers()
      .then(setUsers)
      .catch((err) => setError(apiErrorMessage(err) ?? t("auth.error.generic")))
  }, [t])

  function handleUpdated(updated: User) {
    setUsers((prev) => prev?.map((u) => (u.id === updated.id ? updated : u)) ?? prev)
  }

  if (error) return <p className="text-sm font-semibold text-rose-600">{error}</p>
  if (!users) return <p className="text-sm text-faint">{t("admin.users.loading")}</p>

  return (
    <div>
      {users.map((user) => (
        <AdminUserRow key={user.id} user={user} onUpdated={handleUpdated} />
      ))}
    </div>
  )
}
