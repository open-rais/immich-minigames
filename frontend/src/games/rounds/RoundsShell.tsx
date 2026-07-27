import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"

import { BackButton } from "../shared/BackButton"

interface RoundsShellProps {
  gameTitle: string
  modeTitle: string
  score: number
  onBack: () => void
  // Unused until F2 (Geoguessr/Dateguessr's round stepper) - kept optional now so that phase
  // doesn't need to touch this file at all, only pass the prop.
  stepper?: ReactNode
  children: ReactNode
}

// Chrome shared by every game's rounds review (ROUNDS-VIEW.md roadmap #10) - header mirrors
// menu/LeaderboardPage.tsx's (generic feature title as h1, game+mode as h2). Deliberately no
// max-w-* around children: Geoguessr/Dateguessr's review (F2) reuses MapPicker/TimelineRuler,
// which are fixed-position full-screen components (§5 of the doc) - the width constraint belongs
// to each <XxxRounds>, not to this shell (MoreOrLess's own list applies its own max-w-md).
export function RoundsShell({ gameTitle, modeTitle, score, onBack, stepper, children }: RoundsShellProps) {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-dvh flex-col items-center gap-6 bg-app-bg px-6 py-10">
      <BackButton label={t("common.back")} onClick={onBack} />
      <div className="mt-14 text-center md:mt-0">
        <h1 className="text-3xl font-bold text-ink">{t("common.rounds.title")}</h1>
        <h2 className="mt-1 text-lg font-semibold text-muted">
          {gameTitle} · {modeTitle}
        </h2>
        <p className="mt-2 text-lg text-muted">{t("common.finished.finalScore", { score })}</p>
      </div>
      {stepper}
      <div className="w-full">{children}</div>
    </div>
  )
}
