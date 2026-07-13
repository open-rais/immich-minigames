import { useTranslation } from "react-i18next"

interface CountBadgeProps {
  value: number
  colorClass?: string
}

export function CountBadge({ value, colorClass = "text-ink" }: CountBadgeProps) {
  const { t } = useTranslation()

  return (
    <div className="flex items-baseline gap-1.5 rounded-full bg-count-bg px-[18px] py-1.5">
      <span className={`font-mono text-[26px] font-bold ${colorClass}`}>{value}</span>
      <span className="text-sm font-semibold text-muted">{t("moreOrLess.unit", { count: value })}</span>
    </div>
  )
}
