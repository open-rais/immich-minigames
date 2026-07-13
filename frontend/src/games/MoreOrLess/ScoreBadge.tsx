import { useTranslation } from "react-i18next"

export function ScoreBadge({ score }: { score: number }) {
  const { t } = useTranslation()

  return (
    <div className="flex items-center gap-2.5 rounded-full bg-badge-bg px-5 py-2.5">
      <span className="text-[13px] font-bold tracking-wide text-badge-label uppercase">{t("moreOrLess.score")}</span>
      <span className="font-mono text-lg font-bold text-badge-value">{score}</span>
    </div>
  )
}
