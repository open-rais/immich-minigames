import { useTranslation } from "react-i18next"
import { useNavigate, useParams } from "react-router-dom"

import { BackButton } from "./BackButton"
import { Button } from "./Button"

// Every game is always rendered under the /:gameType/:mode route (see menu/GameRoute.tsx), so
// IdleScreen/FinishedScreen can read these directly instead of every one of the 5 game components
// having to thread them down as new props.
function useLeaderboardHref(): string {
  const { gameType, mode } = useParams<{ gameType: string; mode: string }>()
  return `/${gameType}/${mode}/leaderboard`
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
}

export function IdleScreen({
  title,
  modeTitle,
  description,
  coverUrl,
  onStart,
  onBack,
  busy,
}: IdleScreenProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const leaderboardHref = useLeaderboardHref()
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
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
        <Button variant="primary" className="w-56 py-3" onClick={onStart} disabled={busy}>
          {t("common.startCta")}
        </Button>
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
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-app-bg px-6 text-center">
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
}

export function FinishedScreen({ score, onPlayAgain, onBack, busy }: FinishedScreenProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const leaderboardHref = useLeaderboardHref()
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
      <BackButton label={t("common.back")} onClick={onBack} />
      <h1 className="text-3xl font-bold text-ink">{t("common.finished.title")}</h1>
      <p className="text-xl text-muted">{t("common.finished.finalScore", { score })}</p>
      <div className="flex flex-col items-stretch gap-3">
        <Button variant="primary" className="w-56 py-3" onClick={onPlayAgain} disabled={busy}>
          {t("common.playAgain")}
        </Button>
        <Button variant="secondary" className="w-56 py-3" onClick={() => navigate(leaderboardHref)}>
          {t("common.leaderboards")}
        </Button>
      </div>
    </div>
  )
}
