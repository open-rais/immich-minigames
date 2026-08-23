import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { getDailyStatus } from "../api/daily"
import { useLiveQuery } from "../api/queryCache"
import type { DailyModeStatusOut, DailyStatusOut } from "../api/types/daily"
import { Button } from "../games/shared/Button"
import { ShareModal } from "../games/shared/ShareModal"
import { DAILY_STATUS_KEY } from "../games/shared/useGameSession"
import { pendingDailyModes } from "./dailyFollowUp"
import { buildShareAllText, dailyShareLink } from "./dailyShareAll"

// What opens right after a daily is finished (menu/DailyGameRoute.tsx owns the timing): the day's
// remaining dailies, so the player can jump straight into the next one instead of walking back to
// the menu - or, once none are left, the same "share all results" text the menu's share button
// builds, since that's the only thing left to do with the day.
//
// Reads the day's status from the same cached "daily-status" key everything else uses: the mode
// that was just finished is already in there (useGameSession's optimistic markDailyFinished), and
// useLiveQuery revalidates on mount anyway, so a mode played in another tab lands too.
export function DailyFollowUpModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { state } = useLiveQuery<DailyStatusOut>(DAILY_STATUS_KEY, getDailyStatus)
  const status = state.status === "loading" ? undefined : state.value
  const [shareText, setShareText] = useState<string | null>(null)
  // Kept in a ref so the share effect below doesn't depend on the caller passing a
  // referentially-stable callback - it would otherwise re-run (and re-fetch every played game) on
  // every render of whoever owns this modal.
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  const pending = pendingDailyModes(status)
  const shareAll = !!status && pending.length === 0

  // Nothing is shown while the share text is being built (one getGame per played mode): a spinner
  // modal for what's usually a few hundred ms would be more jarring than the modal simply
  // appearing once it's ready. A failure stays silent and closes the follow-up entirely - same
  // best-effort convention DailySection.tsx's own share button uses.
  useEffect(() => {
    if (!shareAll || !status) return
    let cancelled = false
    buildShareAllText(t, status, dailyShareLink())
      .then((text) => {
        if (!cancelled) setShareText(text)
      })
      .catch(() => {
        if (!cancelled) onCloseRef.current()
      })
    return () => {
      cancelled = true
    }
    // `status` is a cached object identity that only changes when the day's status actually
    // changes, so this doesn't re-fire on every render.
  }, [shareAll, status, t])

  if (shareAll) {
    return shareText ? <ShareModal text={shareText} onClose={onClose} /> : null
  }
  // Nothing cached yet (the day's status is still in flight) - render nothing for now; the
  // useLiveQuery subscription above re-renders this as soon as it lands.
  if (!status || pending.length === 0) return null

  function subtitleFor(modeStatus: DailyModeStatusOut): string {
    return modeStatus.status === "in_progress" ? t("common.continueCta") : t("mainMenu.notPlayed")
  }

  // Overlay/card shell copied from auth/RecentGamesModal.tsx, rows included - same "pick one of a
  // few games" list, and modals in this app copy that shell rather than sharing a component.
  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-ink/40 px-6 animate-[modal-backdrop-in_200ms_ease-out]"
      onClick={onClose}
    >
      <div
        className="max-h-[80vh] w-full max-w-md overflow-y-auto rounded-2xl border border-line-soft bg-surface p-6 shadow-card animate-[modal-card-in_260ms_ease-out]"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-ink">{t("daily.followUp.title")}</h2>

        <ul className="mt-4 flex flex-col gap-2">
          {pending.map(({ status: modeStatus, game, mode }) => (
            <li key={`${modeStatus.game_type}:${modeStatus.mode}`}>
              <button
                type="button"
                onClick={() => {
                  onClose()
                  navigate(`/daily/${modeStatus.game_type}/${modeStatus.mode}`)
                }}
                className="flex w-full items-center gap-3 rounded-xl border border-line-soft p-3 text-left transition-colors hover:bg-hover-tint"
              >
                {mode.coverUrl ? (
                  <img
                    src={mode.coverUrl}
                    alt=""
                    className="h-10 w-10 flex-none rounded-lg object-cover"
                  />
                ) : (
                  <div className="h-10 w-10 flex-none rounded-lg bg-primary" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink">
                    {`${t(game.gameTitleKey)} - ${t(mode.modeTitleKey)}`}
                  </p>
                  <p className="text-xs text-muted">{subtitleFor(modeStatus)}</p>
                </div>
              </button>
            </li>
          ))}
        </ul>

        <Button variant="secondary" className="mt-6 w-full py-2.5" onClick={onClose}>
          {t("common.back")}
        </Button>
      </div>
    </div>
  )
}
