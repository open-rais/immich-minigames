import { useTranslation } from "react-i18next"

export function ScoreBadge({ score }: { score: number }) {
  const { t } = useTranslation()

  return (
    <div className="fixed top-[18px] right-[18px] z-30 flex items-center gap-2 rounded-full bg-badge-bg px-4 py-2 shadow-card md:top-7 md:right-10 md:gap-2.5 md:px-5 md:py-2.5">
      <span className="text-[11px] font-bold tracking-wide text-badge-label uppercase md:text-[13px]">
        {t("moreOrLess.score")}
      </span>
      <span className="font-mono text-base font-bold text-badge-value md:text-lg">{score}</span>
    </div>
  )
}
