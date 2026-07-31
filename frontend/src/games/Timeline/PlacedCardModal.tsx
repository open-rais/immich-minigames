import { useState } from "react"

import { assetThumbnailUrl } from "../../api/games"
import { Spinner } from "../shared/Spinner"

// Full-photo view for a card already placed on the track (TimelineGame.tsx wires this to a tap on
// any TimelineTrack card) - no zoom needed here, only the central "card to place" wants that (see
// TimelineGame.tsx's AssetPhoto usage). A tap anywhere on the overlay closes it, no separate close
// button, per the roadmap's own wording.
export function PlacedCardModal({
  assetId,
  onClose,
}: {
  assetId: string
  onClose: () => void
}) {
  const [loaded, setLoaded] = useState(false)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-6"
      onClick={onClose}
    >
      <img
        src={assetThumbnailUrl(assetId)}
        alt=""
        draggable={false}
        onLoad={() => setLoaded(true)}
        className={`max-h-full max-w-full object-contain transition-opacity duration-150 select-none ${
          loaded ? "opacity-100" : "opacity-0"
        }`}
      />
      {!loaded && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Spinner className="h-8 w-8" />
        </div>
      )}
    </div>
  )
}
