import { StatCard } from "./StatCard"
import { ValueBadge } from "./ValueBadge"

interface PersonCardProps {
  name: string
  value: number | string
  valueKind: "count" | "date"
  subtitle: string
  thumbnailUrl: string
}

export function PersonCard({ name, value, valueKind, subtitle, thumbnailUrl }: PersonCardProps) {
  return (
    <StatCard thumbnailUrl={thumbnailUrl} name={name} subtitle={subtitle}>
      <ValueBadge value={value} kind={valueKind} />
    </StatCard>
  )
}
