import { useState } from "react"
import { useTranslation } from "react-i18next"

import { revokeInvite } from "../api/admin"
import { apiErrorMessage } from "../api/errors"
import type { InviteOut, InviteStatus } from "../api/types"
import { Button } from "../games/shared/Button"

// Same green/amber/red semantic tokens the game clues already use (Immichdle/MoreOrLess) - reused
// here rather than introducing new ad-hoc colors, per CLAUDE.md's design-token convention.
const statusClass: Record<InviteStatus, string> = {
  used: "text-clue-match",
  pending: "text-clue-close",
  expired: "text-clue-miss",
}

interface AdminInviteRowProps {
  invite: InviteOut
  onRevoked: (id: string) => void
}

// Roadmap #H, F1 - one row per invite in AdminInvitesSection.tsx's list. Only a pending invite can
// be revoked (mirrors backend/src/services/invite_service.py's revoke_invite - already-used ones
// are history, not actionable).
export function AdminInviteRow({ invite, onRevoked }: AdminInviteRowProps) {
  const { t, i18n } = useTranslation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const dateLabel =
    invite.status === "used" && invite.used_at
      ? t("admin.invites.usedAt", { date: new Date(invite.used_at).toLocaleDateString(i18n.language) })
      : t("admin.invites.expiresAt", { date: new Date(invite.expires_at).toLocaleDateString(i18n.language) })

  async function handleRevoke() {
    setBusy(true)
    setError(null)
    try {
      await revokeInvite(invite.id)
      onRevoked(invite.id)
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
      setBusy(false)
    }
  }

  return (
    <div className="mt-2 flex items-center justify-between gap-3 rounded-xl border border-line-soft px-4 py-3">
      <div>
        <span className={`text-sm font-semibold ${statusClass[invite.status]}`}>
          {t(`admin.invites.status.${invite.status}`)}
        </span>
        <p className="mt-0.5 text-xs text-faint">{dateLabel}</p>
        {error && <p className="mt-1 text-xs font-semibold text-rose-600">{error}</p>}
      </div>
      {invite.status === "pending" && (
        <Button variant="secondary" className="px-4 py-2 text-sm" onClick={handleRevoke} disabled={busy}>
          {t("admin.invites.revoke")}
        </Button>
      )}
    </div>
  )
}
