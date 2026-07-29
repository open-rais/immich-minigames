import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { createInvite, listInvites } from "../api/admin"
import { apiErrorMessage } from "../api/errors"
import type { InviteOut } from "../api/types"
import { Button } from "../games/shared/Button"
import { ShareModal } from "../games/shared/ShareModal"
import { AdminInviteRow } from "./AdminInviteRow"

// Roadmap #H, F1 - content of the "Invitaciones" top-level accordion in AdminPage.tsx. Generating
// an invite shows its one-time link via ShareModal.tsx (already built for the daily-share feature -
// a generic "here's some text, copy it" modal, reused as-is rather than building a new one).
export function AdminInvitesSection() {
  const { t } = useTranslation()
  const [invites, setInvites] = useState<InviteOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [newLink, setNewLink] = useState<string | null>(null)

  useEffect(() => {
    listInvites()
      .then(setInvites)
      .catch((err) => setError(apiErrorMessage(err) ?? t("auth.error.generic")))
  }, [t])

  async function handleGenerate() {
    setBusy(true)
    setError(null)
    try {
      const created = await createInvite()
      setNewLink(`${window.location.origin}/signup?invite=${created.token}`)
      setInvites(await listInvites())
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
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

      {error && <p className="mt-3 text-sm font-semibold text-rose-600">{error}</p>}

      {!invites ? (
        <p className="mt-3 text-sm text-faint">{t("admin.invites.loading")}</p>
      ) : invites.length === 0 ? (
        <p className="mt-3 text-sm text-faint">{t("admin.invites.empty")}</p>
      ) : (
        invites.map((invite) => <AdminInviteRow key={invite.id} invite={invite} onRevoked={handleRevoked} />)
      )}

      {newLink && <ShareModal text={newLink} onClose={() => setNewLink(null)} />}
    </div>
  )
}
