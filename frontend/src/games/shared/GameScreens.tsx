import type { ReactNode } from "react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useLocation, useNavigate, useParams } from "react-router-dom"

import { getGame } from "../../api/games"
import { BackButton } from "./BackButton"
import { Button } from "./Button"
import { buildDailyShareMessage } from "./dailyShareText"
import { ShareModal } from "./ShareModal"

// Every game is always rendered under the /:gameType/:mode route (see menu/GameRoute.tsx), so
// IdleScreen/FinishedScreen can read these directly instead of every one of the 5 game components
// having to thread them down as new props. A daily game is rendered under
// /daily/:gameType/:mode instead (menu/DailyGameRoute.tsx) and needs its own leaderboard route
// (/daily/:gameType/:mode/leaderboard, menu/DailyLeaderboardPage.tsx) - detected off the actual
// matched path rather than threading a `daily` prop through every *Game.tsx's IdleScreen/
// FinishedScreen call just for this.
function useLeaderboardHref(): string {
  const { gameType, mode } = useParams<{ gameType: string; mode: string }>()
  const { pathname } = useLocation()
  const prefix = pathname.startsWith("/daily/") ? "/daily" : ""
  return `${prefix}/${gameType}/${mode}/leaderboard`
}

// Null unless the caller says this mode has a roundsComponent
// registered (see games/catalog.ts's CatalogMode) *and* passed a gameId. Whether a roundsComponent
// exists is looked up once in GameRoute.tsx and threaded down as `hasRoundsView`, the same way
// GameRoute already threads down `coverUrl` - not looked up here directly, which would make this
// game-tree module import games/catalog.ts, which imports every *Game.tsx (a cycle).
function useRoundsHref(
  gameId: string | undefined,
  hasRoundsView: boolean | undefined,
): string | null {
  const { gameType, mode } = useParams<{ gameType: string; mode: string }>()
  if (!gameId || !hasRoundsView || !gameType || !mode) return null
  return `/${gameType}/${mode}/game/${gameId}/rounds`
}

// The idle / error / finished full-screen states are identical across every game (only the title
// and start-description differ), so they live here instead of being copy-pasted into each game
// component. Game-specific strings are passed in already translated; everything else comes from the
// shared `common.*` i18n namespace.

interface IdleScreenProps {
  title: string
  modeTitle: string
  description: string
  coverUrl?: string
  onStart: () => void
  onBack: () => void
  busy: boolean
  // Whether the current player (owner or account) has an unfinished game for this
  // mode. Both optional/default-omitted (undefined behaves like false), so a caller with no
  // resuming wired up simply never shows "Continuar". `null` (still checking)
  // also renders like false - an accepted brief "plain layout, then Continue pops in" flash rather
  // than a loading spinner.
  hasCurrentGame?: boolean | null
  onContinue?: () => void
  // Daily games have no "Nuevo juego" concept (one attempt only) - hides that secondary action
  // even when hasCurrentGame is true, leaving just "Continuar". Every normal game keeps the
  // default (true).
  allowNewGame?: boolean
}

export function IdleScreen({
  title,
  modeTitle,
  description,
  coverUrl,
  onStart,
  onBack,
  busy,
  hasCurrentGame,
  onContinue,
  allowNewGame = true,
}: IdleScreenProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const leaderboardHref = useLeaderboardHref()
  const canContinue = !!hasCurrentGame && !!onContinue
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
      <BackButton label={t("common.back")} onClick={onBack} />
      {coverUrl && (
        <img src={coverUrl} alt="" className="h-28 w-28 rounded-2xl object-cover shadow-card" />
      )}
      <div>
        <h1 className="text-3xl font-bold text-ink">{title}</h1>
        <h2 className="mt-1 text-lg font-semibold text-muted">{modeTitle}</h2>
      </div>
      <p className="max-w-md text-muted">{description}</p>
      <div className="flex flex-col items-stretch gap-3">
        {canContinue && (
          <Button variant="primary" className="w-56 py-3" onClick={onContinue} disabled={busy}>
            {t("common.continueCta")}
          </Button>
        )}
        {(!canContinue || allowNewGame) && (
          <Button
            variant={canContinue ? "secondary" : "primary"}
            className="w-56 py-3"
            onClick={onStart}
            disabled={busy}
          >
            {t(canContinue ? "common.newGameCta" : "common.startCta")}
          </Button>
        )}
        <Button variant="secondary" className="w-56 py-3" onClick={() => navigate(leaderboardHref)}>
          {t("common.leaderboards")}
        </Button>
      </div>
    </div>
  )
}

interface ErrorScreenProps {
  onRetry: () => void
  onBack: () => void
  busy: boolean
}

export function ErrorScreen({ onRetry, onBack, busy }: ErrorScreenProps) {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-app-bg px-6 text-center">
      <BackButton label={t("common.back")} onClick={onBack} />
      <p className="text-body">{t("common.error.message")}</p>
      <Button variant="primary" className="px-6 py-3" onClick={onRetry} disabled={busy}>
        {t("common.error.retry")}
      </Button>
    </div>
  )
}

interface FinishedScreenProps {
  score: number
  onPlayAgain: () => void
  onBack: () => void
  busy: boolean
  // Overrides the default "common.finished.title" heading - e.g. Immichdle's won/lost-specific
  // copy. Left unset for every other game, which shares the plain generic title.
  title?: string
  // Extra content shown between the title and the score line - e.g. Immichdle's revealed target
  // person (face + name). Undefined for every other game.
  children?: ReactNode
  // The just-finished game's id - shows a "Ver rondas" button when present *and*
  // hasRoundsView is true (see useRoundsHref above). Every game passes gameId now; the button
  // itself only lights up once a mode registers its roundsComponent.
  gameId?: string
  // Forwarded from GameComponentProps (see games/catalog.ts/GameRoute.tsx) - whether the current
  // mode has a roundsComponent registered at all.
  hasRoundsView?: boolean
  // Daily games have no replay (one attempt only) - hides "Jugar de nuevo" entirely.
  // Every normal game keeps the default (true).
  allowPlayAgain?: boolean
  // Shows a "Compartir" button when set (daily games only, see each *Game.tsx's
  // FinishedScreen call). gameTitle/modeTitle are passed in already-translated (the same strings
  // each *Game.tsx already computes for its own IdleScreen title) rather than looked up here via
  // games/catalog.ts, which would cycle back through every *Game.tsx (see useRoundsHref above).
  dailyShare?: {
    gameId: string
    gameType: string
    mode: string
    gameTitle: string
    modeTitle: string
  }
}

export function FinishedScreen({
  score,
  onPlayAgain,
  onBack,
  busy,
  title,
  children,
  gameId,
  hasRoundsView,
  allowPlayAgain = true,
  dailyShare,
}: FinishedScreenProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const leaderboardHref = useLeaderboardHref()
  const roundsHref = useRoundsHref(gameId, hasRoundsView)
  const [shareBusy, setShareBusy] = useState(false)
  const [shareText, setShareText] = useState<string | null>(null)
  const [shareError, setShareError] = useState(false)

  async function handleShare() {
    if (!dailyShare) return
    setShareBusy(true)
    setShareError(false)
    try {
      const g = await getGame(dailyShare.gameId)
      const link = `${window.location.origin}/daily/${dailyShare.gameType}/${dailyShare.mode}`
      setShareText(buildDailyShareMessage(t, g, dailyShare.gameTitle, dailyShare.modeTitle, link))
    } catch {
      setShareError(true)
    } finally {
      setShareBusy(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
      <BackButton label={t("common.back")} onClick={onBack} />
      <h1 className="text-3xl font-bold text-ink">{title ?? t("common.finished.title")}</h1>
      {children}
      <p className="text-xl text-muted">{t("common.finished.finalScore", { score })}</p>
      <div className="flex flex-col items-stretch gap-3">
        {allowPlayAgain && (
          <Button variant="primary" className="w-56 py-3" onClick={onPlayAgain} disabled={busy}>
            {t("common.playAgain")}
          </Button>
        )}
        {dailyShare && (
          <Button
            variant="primary"
            className="w-56 py-3"
            onClick={handleShare}
            disabled={shareBusy}
          >
            {t("daily.share.button")}
          </Button>
        )}
        {roundsHref && (
          <Button variant="secondary" className="w-56 py-3" onClick={() => navigate(roundsHref)}>
            {t("common.viewRounds")}
          </Button>
        )}
        <Button variant="secondary" className="w-56 py-3" onClick={() => navigate(leaderboardHref)}>
          {t("common.leaderboards")}
        </Button>
      </div>
      {shareError && (
        <p className="text-sm font-semibold text-rose-600">{t("daily.share.error")}</p>
      )}
      {shareText && <ShareModal text={shareText} onClose={() => setShareText(null)} />}
    </div>
  )
}
