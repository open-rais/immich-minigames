import { useTranslation } from "react-i18next"

import type { MoreOrLessGuess } from "../../api/types"
import { Button } from "../shared/Button"
import { CountBadge } from "./CountBadge"
import { StatCard } from "./StatCard"

export type CandidatePhase = "guessing" | "counting" | "revealed"

interface CandidateCardProps {
  name: string
  thumbnailUrl: string
  phase: CandidatePhase
  displayCount: number
  correct: boolean | null
  onGuess: (guess: MoreOrLessGuess) => void
}

export function CandidateCard({ name, thumbnailUrl, phase, displayCount, correct, onGuess }: CandidateCardProps) {
  const { t } = useTranslation()

  // Only the number itself changes color on reveal - the card border/badge stay neutral.
  const countColorClass = phase === "revealed" ? (correct ? "text-emerald-600" : "text-rose-600") : "text-ink"

  return (
    <StatCard thumbnailUrl={thumbnailUrl} name={name} subtitle={t("moreOrLess.question", { name })}>
      {phase === "guessing" ? (
        <div className="flex w-full gap-2.5">
          <Button variant="primary" className="flex-1 py-4 md:py-3" onClick={() => onGuess("more")}>
            {t("moreOrLess.guessMore")}
          </Button>
          <Button variant="secondary" className="flex-1 py-4 md:py-3" onClick={() => onGuess("less")}>
            {t("moreOrLess.guessLess")}
          </Button>
        </div>
      ) : (
        <CountBadge value={displayCount} colorClass={countColorClass} />
      )}
    </StatCard>
  )
}
