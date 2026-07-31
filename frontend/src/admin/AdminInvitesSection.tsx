import { useState } from "react"
import { useTranslation } from "react-i18next"

import { createInvite, listInvites } from "../api/admin"
import { apiErrorMessage } from "../api/errors"
import type { InviteOut } from "../api/types/admin"
import { Button } from "../games/shared/Button"
import { ShareModal } from "../games/shared/ShareModal"
import { AdminInviteRow } from "./AdminInviteRow"
import { useInfiniteAdminList } from "./useInfiniteAdminList"

// Content of the "Invitaciones" top-level accordion in AdminPage.tsx. Generating
// an invite shows its one-time link via ShareModal.tsx (already built for the daily-share feature -
// a generic "here's some text, copy it" modal, reused as-is rather than building a new one).
// Infinite-scroll paginated (see useInfiniteAdminList.ts) - capped at ~5 rows tall, scrolling near
// the bottom loads the next page.
export function AdminInvitesSection() {
  const { t } = useTranslation()
  const {
    items: invites,
    error,
    loadingMore,
    containerRef,
    onScroll,
    setItems: setInvites,
    reload,
  } = useInfiniteAdminList<InviteOut>((offset, limit) => listInvites({ offset, limit }))
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [newLink, setNewLink] = useState<string | null>(null)

  async function handleGenerate() {
    setBusy(true)
    setGenerateError(null)
    try {
      const created = await createInvite()
      setNewLink(`${window.location.origin}/signup?invite=${created.token}`)
      reload() // the fresh invite sorts first (newest-first order), so it lands on page 1
    } catch (err) {
      setGenerateError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  function handleRevoked(id: string) {
    setInvites((prev) => prev?.filter((i) => i.id !== id) ?? prev)
  }

  return (
    <div>
      <Button variant="primary" className="w-full py-2.5" onClick={handleGenerate} disabled={busy}>
        {t("admin.invites.generate")}
      </Button>

      {generateError && <p className="mt-3 text-sm font-semibold text-rose-600">{generateError}</p>}
      {error && <p className="mt-3 text-sm font-semibold text-rose-600">{error}</p>}

      {!invites ? (
        <p className="mt-3 text-sm text-faint">{t("admin.invites.loading")}</p>
      ) : invites.length === 0 ? (
        <p className="mt-3 text-sm text-faint">{t("admin.invites.empty")}</p>
      ) : (
        <div
          ref={containerRef}
          onScroll={onScroll}
          // ~5 rows of AdminInviteRow's fixed height - approximate, not derived from exact math,
          // same looseness games/shared/PersonSearchInput.tsx's own max-h accepts.
          className="max-h-[350px] overflow-y-auto overscroll-contain"
        >
          {invites.map((invite) => (
            <AdminInviteRow key={invite.id} invite={invite} onRevoked={handleRevoked} />
          ))}
          {loadingMore && <p className="mt-2 text-sm text-faint">{t("admin.invites.loading")}</p>}
        </div>
      )}

      {newLink && <ShareModal text={newLink} onClose={() => setNewLink(null)} />}
    </div>
  )
}
