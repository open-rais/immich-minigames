import { useTranslation } from "react-i18next"

import { BackButton } from "./BackButton"
import { Button } from "./Button"

// The idle / error / finished full-screen states are identical across every game (only the title
// and start-description differ), so they live here instead of being copy-pasted into each game
// component. Game-specific strings are passed in already translated; everything else comes from the
// shared `common.*` i18n namespace.

interface IdleScreenProps {
  title: string
  description: string
  onStart: () => void
  onBack: () => void
  busy: boolean
}

export function IdleScreen({ title, description, onStart, onBack, busy }: IdleScreenProps) {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
      <BackButton label={t("common.back")} onClick={onBack} />
      <h1 className="text-3xl font-bold text-ink">{title}</h1>
      <p className="max-w-md text-muted">{description}</p>
      <Button variant="primary" className="px-8 py-3" onClick={onStart} disabled={busy}>
        {t("common.startCta")}
      </Button>
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
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
      <BackButton label={t("common.back")} onClick={onBack} />
      <h1 className="text-3xl font-bold text-ink">{t("common.finished.title")}</h1>
      <p className="text-xl text-muted">{t("common.finished.finalScore", { score })}</p>
      <Button variant="primary" className="px-8 py-3" onClick={onPlayAgain} disabled={busy}>
        {t("common.playAgain")}
      </Button>
    </div>
  )
}
