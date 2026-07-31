import { useTranslation } from "react-i18next"

import { listUsers } from "../api/admin"
import type { User } from "../api/types/auth"
import { AdminUserRow } from "./AdminUserRow"
import { useInfiniteAdminList } from "./useInfiniteAdminList"

// Content of the "Usuarios" top-level accordion in
// AdminPage.tsx. Mounts lazily (SettingAccordion only mounts children on first expand), so the
// list isn't fetched until the admin actually opens this section. Infinite-scroll paginated (see
// useInfiniteAdminList.ts) - capped at ~5 rows tall, scrolling near the bottom loads the next page.
export function AdminUsersSection() {
  const { t } = useTranslation()
  const {
    items: users,
    error,
    loadingMore,
    containerRef,
    onScroll,
    setItems: setUsers,
  } = useInfiniteAdminList<User>((offset, limit) => listUsers({ offset, limit }))

  function handleUpdated(updated: User) {
    setUsers((prev) => prev?.map((u) => (u.id === updated.id ? updated : u)) ?? prev)
  }

  if (error) return <p className="text-sm font-semibold text-rose-600">{error}</p>
  if (!users) return <p className="text-sm text-faint">{t("admin.users.loading")}</p>

  return (
    <div
      ref={containerRef}
      onScroll={onScroll}
      // ~5 rows of AdminUserRow's collapsed (nested SettingAccordion) height - approximate, not
      // derived from exact math, same looseness games/shared/PersonSearchInput.tsx's own max-h
      // accepts for its results box.
      className="max-h-[420px] overflow-y-auto overscroll-contain"
    >
      {users.map((user) => (
        <AdminUserRow key={user.id} user={user} onUpdated={handleUpdated} />
      ))}
      {loadingMore && <p className="mt-3 text-sm text-faint">{t("admin.users.loading")}</p>}
    </div>
  )
}
