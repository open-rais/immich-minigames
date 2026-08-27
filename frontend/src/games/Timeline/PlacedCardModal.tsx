import { assetThumbnailUrl } from "../../api/games"
import { useImageLoad } from "../shared/imageLoading"
import { PhotoError } from "../shared/PhotoError"
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
  // Shares AssetPhoto's load/timeout/retry machinery (imageLoading.ts). Before that existed this
  // screen had no onError at all, so a photo that failed - not just one that stalled - left the
  // spinner up forever.
  const src = assetThumbnailUrl(assetId)
  const { status, imgRef, imgKey, onLoad, onError, retry } = useImageLoad(src)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-6"
      onClick={onClose}
    >
      {status === "failed" ? (
        // Stops the tap that hits "Reintentar" from also closing the modal underneath it.
        <div className="absolute inset-6" onClick={(e) => e.stopPropagation()}>
          <PhotoError onRetry={retry} />
        </div>
      ) : (
        <img
          key={imgKey}
          ref={imgRef}
          src={src}
          alt=""
          draggable={false}
          onLoad={onLoad}
          onError={onError}
          className={`max-h-full max-w-full object-contain transition-opacity duration-150 select-none ${
            status === "loaded" ? "opacity-100" : "opacity-0"
          }`}
        />
      )}
      {status === "loading" && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Spinner className="h-8 w-8" />
        </div>
      )}
    </div>
  )
}
