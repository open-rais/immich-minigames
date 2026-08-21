import { useTranslation } from "react-i18next"

// The post-guess result card (points earned + a game-specific subtitle) shown once a Geoguessr/
// Dateguessr round is revealed. The two games only differ in the subtitle text ("N km away" vs.
// "N days off") and where the card sits, both passed in - the shell is shared.
interface RevealResultCardProps {
  scoreDelta: number
  subtitle: string
  // Positioning is game-specific (it hugs whichever picker that game uses), so callers supply the
  // fixed-position utility classes rather than baking one game's layout in here.
  positionClassName: string
  // A third, fainter line under subtitle - optional, so every existing caller (Geoguessr/
  // Dateguessr/Timeline) is unaffected. Trivium's rounds review uses it for "answered in N.Ns",
  // a detail the live-play card doesn't need (the timer bar right above it already shows that).
  detail?: string
}

export function RevealResultCard({
  scoreDelta,
  subtitle,
  positionClassName,
  detail,
}: RevealResultCardProps) {
  const { t } = useTranslation()
  return (
    <div className={`fixed z-30 ${positionClassName}`}>
      <div className="rounded-2xl border border-line bg-surface px-5 py-3 text-left shadow-card">
        <p className="font-mono text-lg font-bold text-ink">
          {t("common.points", { score: scoreDelta })}
        </p>
        <p className="text-sm font-semibold text-muted">{subtitle}</p>
        {detail && <p className="text-xs text-faint">{detail}</p>}
      </div>
    </div>
  )
}
