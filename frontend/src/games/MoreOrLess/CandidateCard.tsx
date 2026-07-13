import { useTranslation } from "react-i18next"

import type { Guess } from "../../api/types"
import { PersonPhoto } from "./PersonPhoto"

export type CandidatePhase = "guessing" | "counting" | "revealed"

interface CandidateCardProps {
  name: string
  thumbnailUrl: string
  phase: CandidatePhase
  displayCount: number
  correct: boolean | null
  onGuess: (guess: Guess) => void
}

const primaryButtonClass =
  "flex-1 rounded-full bg-primary py-4 text-[15px] font-bold text-white transition-colors hover:bg-primary-hover md:py-3"
const secondaryButtonClass =
  "flex-1 rounded-full border border-line-soft bg-white py-4 text-[15px] font-bold text-body transition-colors hover:bg-hover-tint md:py-3"

export function CandidateCard({ name, thumbnailUrl, phase, displayCount, correct, onGuess }: CandidateCardProps) {
  const { t } = useTranslation()

  // Only the number itself changes color on reveal - the card border/badge stay neutral.
  const countTextClass = phase === "revealed" ? (correct ? "text-emerald-600" : "text-rose-600") : "text-ink"

  return (
    <div className="flex h-full min-h-0 w-full flex-col items-center gap-3.5 rounded-[22px] border border-line bg-white p-[18px] shadow-card md:h-auto md:w-[300px] md:rounded-3xl md:p-5">
      <PersonPhoto src={thumbnailUrl} alt={name} />

      <div className="flex min-h-[56px] w-full items-center justify-center">
        <div className="text-center text-xl font-bold text-ink">{name}</div>
      </div>

      <div className="flex min-h-[44px] w-full items-center justify-center">
        <p className="text-center text-sm font-semibold text-muted">{t("moreOrLess.question", { name })}</p>
      </div>

      <div className="flex min-h-[52px] w-full items-center justify-center">
        {phase === "guessing" ? (
          <div className="flex w-full gap-2.5">
            <button onClick={() => onGuess("more")} className={primaryButtonClass}>
              {t("moreOrLess.guessMore")}
            </button>
            <button onClick={() => onGuess("less")} className={secondaryButtonClass}>
              {t("moreOrLess.guessLess")}
            </button>
          </div>
        ) : (
          <div className="flex items-baseline gap-1.5 rounded-full bg-count-bg px-[18px] py-1.5">
            <span className={`font-mono text-[26px] font-bold ${countTextClass}`}>{displayCount}</span>
            <span className="text-sm font-semibold text-muted">{t("moreOrLess.unit", { count: displayCount })}</span>
          </div>
        )}
      </div>
    </div>
  )
}
