import { useTranslation } from "react-i18next"

interface RoundStepperProps {
  current: number
  total: number
  onPrev: () => void
  onNext: () => void
}

const ARROW_BUTTON_CLASS =
  "flex h-9 w-9 items-center justify-center rounded-full border border-line-strong bg-surface text-body shadow-card transition-colors hover:bg-hover-tint disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-surface"

// Interactive counterpart to games/shared/RoundBadge.tsx (same top-center fixed slot/pill shown
// during real gameplay) - this one lets the player step back and forth through already-played
// rounds instead of only ever advancing (ROUNDS-VIEW.md roadmap #10, "one round at a time" family:
// Geoguessr/Dateguessr today, WhosThatPerson later).
export function RoundStepper({ current, total, onPrev, onNext }: RoundStepperProps) {
  const { t } = useTranslation()
  return (
    <div className="fixed top-[18px] left-1/2 z-30 flex -translate-x-1/2 items-center gap-2 md:top-7">
      <button onClick={onPrev} disabled={current <= 1} aria-label={t("common.previousRound")} className={ARROW_BUTTON_CLASS}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>
      <div className="rounded-full bg-badge-bg px-4 py-2 shadow-card">
        <span className="text-[11px] font-bold tracking-wide text-badge-label uppercase md:text-[13px]">
          {t("common.roundOf", { current, total })}
        </span>
      </div>
      <button onClick={onNext} disabled={current >= total} aria-label={t("common.nextRound")} className={ARROW_BUTTON_CLASS}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 18l6-6-6-6" />
        </svg>
      </button>
    </div>
  )
}
