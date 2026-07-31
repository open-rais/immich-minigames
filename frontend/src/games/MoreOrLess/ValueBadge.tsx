import { useTranslation } from "react-i18next"

import { formatBirthDate } from "./birthDate"

interface ValueBadgeProps {
  value: number | string
  // "count" - value is a plain asset count, rendered with its pluralized unit (moreOrLess.unit).
  // "date" - value is an ISO-8601 "YYYY-MM-DD" birth date string, formatted for display.
  kind: "count" | "date"
  colorClass?: string
}

export function ValueBadge({ value, kind, colorClass = "text-ink" }: ValueBadgeProps) {
  const { t, i18n } = useTranslation()

  const text = kind === "date" ? formatBirthDate(value as string, i18n.language) : value

  return (
    <div className="flex items-baseline gap-1.5 rounded-full bg-count-bg px-[18px] py-1.5">
      <span className={`font-mono text-[26px] font-bold ${colorClass}`}>{text}</span>
      {kind === "count" && (
        <span className="text-sm font-semibold text-muted">
          {t("moreOrLess.unit", { count: value as number })}
        </span>
      )}
    </div>
  )
}
