import { useMemo, useState } from "react"
import { useTranslation } from "react-i18next"

import { apiErrorMessage } from "../api/errors"
import { personThumbnailUrl } from "../api/games"
import { Button } from "../games/shared/Button"
import { PersonAvatar } from "../games/shared/PersonAvatar"
import { PersonSearchInput } from "../games/shared/PersonSearchInput"
import { useAuth } from "./useAuth"

// Cosmetic avatar picker (roadmap point E) - any Person from the Immich library, shown in the
// header's user circle (see menu/UserMenu.tsx). Kept as its own component rather than inlined
// into ProfilePage so that page's JSX doesn't balloon; reuses the same PersonSearchInput already
// used by Immichdle/WhosThatPerson (renamed onGuess -> onSelect since it's genuinely general-
// purpose "pick a person", not just for guessing).
export function SkinPicker() {
  const { t } = useTranslation()
  const { user, updateSkin } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Stable ref per skin id (not a literal `new Set()` every render) - PersonSearchInput's
  // debounced search effect depends on this by reference, same reasoning as
  // WhosThatPerson/FaceGuessPopover.tsx's EMPTY_EXCLUDE_IDS.
  const excludeIds = useMemo(
    () => (user?.skin_person_id ? new Set([user.skin_person_id]) : new Set<string>()),
    [user?.skin_person_id],
  )

  if (!user) return null

  async function apply(personId: string | null) {
    setBusy(true)
    setError(null)
    try {
      await updateSkin(personId)
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  return (
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
          <Button variant="secondary" className="px-4 py-2 text-sm" onClick={() => apply(null)} disabled={busy}>
            {t("auth.profile.skin.clear")}
          </Button>
        )}
      </div>
      <PersonSearchInput excludeIds={excludeIds} onSelect={apply} disabled={busy} />
      {error && <p className="text-sm font-semibold text-rose-600">{error}</p>}
    </div>
  )
}
