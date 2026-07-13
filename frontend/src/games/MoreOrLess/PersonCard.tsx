import { useTranslation } from "react-i18next"

import { PersonPhoto } from "./PersonPhoto"

interface PersonCardProps {
  name: string
  assetCount: number
  thumbnailUrl: string
}

export function PersonCard({ name, assetCount, thumbnailUrl }: PersonCardProps) {
  const { t } = useTranslation()

  return (
    <div className="flex w-[300px] flex-col items-center gap-3.5 rounded-3xl border border-line bg-white p-5 shadow-card">
      <PersonPhoto src={thumbnailUrl} alt={name} />

      {/* Fixed-height rows shared with CandidateCard's name/question/action rows (names and
          questions can wrap to 1 or 2 lines depending on the person) so both cards in the row
          always end up the same total height. */}
      <div className="flex min-h-[56px] w-full items-center justify-center">
        <div className="text-center text-xl font-bold text-ink">{name}</div>
      </div>

      <div className="flex min-h-[44px] w-full items-center justify-center">
        <p className="text-center text-sm font-semibold text-muted">{t("moreOrLess.has")}</p>
      </div>

      <div className="flex min-h-[52px] w-full items-center justify-center">
        <div className="flex items-baseline gap-1.5 rounded-full bg-count-bg px-[18px] py-1.5">
          <span className="font-mono text-[26px] font-bold text-ink">{assetCount}</span>
          <span className="text-sm font-semibold text-muted">{t("moreOrLess.unit", { count: assetCount })}</span>
        </div>
      </div>
    </div>
  )
}
