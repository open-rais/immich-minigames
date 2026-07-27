import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"

import { BackButton } from "../shared/BackButton"

interface RoundsShellProps {
  gameTitle: string
  modeTitle: string
  score: number
  onBack: () => void
  children: ReactNode
}

// Chrome for the "full list" rounds-review family (MoreOrLess, Immichdle - ROUNDS-VIEW.md §2)-
// header mirrors menu/LeaderboardPage.tsx's (generic feature title as h1, game+mode as h2). The
// "one round at a time" family (Geoguessr/Dateguessr/Who'sThatPerson) never reaches this shell at
// all - RoundsPage.tsx renders those <XxxRounds> directly, since MapPicker/TimelineRuler/AssetPhoto
// are all fixed-position full-viewport components (§5 of the doc) that don't belong inside this
// shell's padded, centered, min-h-dvh column, and their own round stepper needs live state only
// the component itself holds. Deliberately no max-w-* around children either way - MoreOrLess's
// own list applies its own max-w-md.
export function RoundsShell({ gameTitle, modeTitle, score, onBack, children }: RoundsShellProps) {
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
      <div className="w-full">{children}</div>
    </div>
  )
}
