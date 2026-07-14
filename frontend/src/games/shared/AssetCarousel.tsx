import { useState } from "react"
import { useTranslation } from "react-i18next"

import { assetThumbnailUrl } from "../../api/games"
import { AssetPhoto } from "./AssetPhoto"

// Round-scoped photo browser: up to 5 photos per round (games/asset_rounds.py's
// MAX_EXTRA_ASSETS), main "answer" asset first. Purely for the player to look around - it never
// affects the guess or the score. Mount with `key={round.id}` so `index` resets to 0 on every new
// round without extra plumbing (same pattern AssetPhoto itself uses `key={assetId}` for).
export function AssetCarousel({ assetIds, alt }: { assetIds: string[]; alt: string }) {
  const { t } = useTranslation()
  const [index, setIndex] = useState(0)

  const showArrows = assetIds.length > 1
  const isFirst = index === 0
  const isLast = index === assetIds.length - 1
  const goPrev = () => setIndex((i) => Math.max(i - 1, 0))
  const goNext = () => setIndex((i) => Math.min(i + 1, assetIds.length - 1))

  return (
    <>
      <AssetPhoto src={assetThumbnailUrl(assetIds[index])} alt={alt} />
      {showArrows && (
        <>
          <button
            onClick={goPrev}
            disabled={isFirst}
            aria-label={t("common.previousPhoto")}
            className="fixed top-1/2 left-[18px] z-20 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full border border-line-strong bg-surface text-body shadow-card transition-colors hover:bg-hover-tint disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-surface md:left-10"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 18l-6-6 6-6" />
            </svg>
          </button>
          <button
            onClick={goNext}
            disabled={isLast}
            aria-label={t("common.nextPhoto")}
            className="fixed top-1/2 right-[18px] z-20 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full border border-line-strong bg-surface text-body shadow-card transition-colors hover:bg-hover-tint disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-surface md:right-10"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>
        </>
      )}
    </>
  )
}
