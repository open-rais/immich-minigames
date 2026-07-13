import { useTranslation } from "react-i18next"

// The "Round X of Y" pill shown top-center during a Geoguessr/Dateguessr round - identical in both,
// so it lives here rather than being duplicated in each game component.
export function RoundBadge({ current, total }: { current: number; total: number }) {
  const { t } = useTranslation()
  return (
    <div className="fixed top-[18px] left-1/2 z-30 -translate-x-1/2 rounded-full bg-badge-bg px-4 py-2 shadow-card md:top-7">
      <span className="text-[11px] font-bold tracking-wide text-badge-label uppercase md:text-[13px]">
        {t("common.roundOf", { current, total })}
      </span>
    </div>
  )
}
