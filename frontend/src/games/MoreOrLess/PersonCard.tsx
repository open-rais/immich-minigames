import { useTranslation } from "react-i18next"

import { CountBadge } from "./CountBadge"
import { StatCard } from "./StatCard"

interface PersonCardProps {
  name: string
  assetCount: number
  thumbnailUrl: string
}

export function PersonCard({ name, assetCount, thumbnailUrl }: PersonCardProps) {
  const { t } = useTranslation()

  return (
    <StatCard thumbnailUrl={thumbnailUrl} name={name} subtitle={t("moreOrLess.has")}>
      <CountBadge value={assetCount} />
    </StatCard>
  )
}
