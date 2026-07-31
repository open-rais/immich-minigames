import type { MoreOrLessGuess } from "../../api/types/moreOrLess"
import { Button } from "../shared/Button"
import { StatCard } from "./StatCard"
import { ValueBadge } from "./ValueBadge"

export type CandidatePhase = "guessing" | "counting" | "revealed"

interface CandidateCardProps {
  name: string
  thumbnailUrl: string
  phase: CandidatePhase
  displayValue: number | string
  valueKind: "count" | "date"
  subtitle: string
  moreLabel: string
  lessLabel: string
  correct: boolean | null
  onGuess: (guess: MoreOrLessGuess) => void
}

export function CandidateCard({
  name,
  thumbnailUrl,
  phase,
  displayValue,
  valueKind,
  subtitle,
  moreLabel,
  lessLabel,
  correct,
  onGuess,
}: CandidateCardProps) {
  // Only the value itself changes color on reveal - the card border/badge stay neutral.
  const valueColorClass =
    phase === "revealed" ? (correct ? "text-emerald-600" : "text-rose-600") : "text-ink"

  return (
    <StatCard thumbnailUrl={thumbnailUrl} name={name} subtitle={subtitle}>
      {phase === "guessing" ? (
        <div className="flex w-full gap-2.5">
          <Button
            variant="primary"
            className="flex-1 py-3 md:py-3 flex items-center justify-center gap-2"
            onClick={() => onGuess("more")}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
            {moreLabel}
          </Button>
          <Button
            variant="secondary"
            className="flex-1 py-3 md:py-3 flex items-center justify-center gap-2"
            onClick={() => onGuess("less")}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 5v14M5 12l7 7 7-7" />
            </svg>
            {lessLabel}
          </Button>
        </div>
      ) : (
        <ValueBadge value={displayValue} kind={valueKind} colorClass={valueColorClass} />
      )}
    </StatCard>
  )
}
