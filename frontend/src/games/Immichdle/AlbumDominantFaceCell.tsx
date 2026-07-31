import { personThumbnailUrl } from "../../api/games"
import type { DominantFaceComparison } from "../../api/types/immichdle"
import { PersonAvatar } from "../shared/PersonAvatar"

// Same three-tier fill ClueCell uses (see that component's own variantClass) - re-declared rather
// than imported since this is the one column that isn't a ClueCell tile at all (it needs a face
// thumbnail, which doesn't fit ClueCell's generic centered-text shape) - see
// albumGuessTableColumns.ts for how AlbumGuessTable slots this in alongside the shared ClueCell
// columns.
const variantClass: Record<DominantFaceComparison, string> = {
  match: "bg-clue-match",
  close: "bg-clue-close",
  miss: "bg-clue-miss",
}

interface AlbumDominantFaceCellProps {
  // Plain props (not a whole AlbumdleCluesOut) so this same component renders both a guess row
  // (fed from clues.dominant_face_*) and the target row (fed from the target's own dominant face,
  // always "match" - see AlbumGuessTable.tsx).
  personId: string | null
  name: string | null
  extraCount: number
  comparison: DominantFaceComparison | null
  pending?: boolean
}

export function AlbumDominantFaceCell({
  personId,
  name,
  extraCount,
  comparison,
  pending = false,
}: AlbumDominantFaceCellProps) {
  if (pending) {
    return <div className="aspect-square w-full rounded-xl border border-line bg-count-bg" />
  }

  if (comparison === null || personId === null) {
    // No named face at all in the guessed album - same "amber question mark, no direction to
    // hint at" treatment ClueCell gives an unknown date (see clueColors.ts's dateClue).
    return (
      <div className="relative flex aspect-square w-full items-center justify-center overflow-hidden rounded-xl bg-clue-close">
        <span className="relative z-10 text-lg font-bold text-white">?</span>
      </div>
    )
  }

  return (
    <div
      className={`flex aspect-square w-full flex-col items-center justify-center gap-0.5 overflow-hidden rounded-xl p-1 ${variantClass[comparison]}`}
    >
      <PersonAvatar src={personThumbnailUrl(personId)} alt={name ?? ""} size="sm" />
      <span className="line-clamp-1 px-0.5 text-center text-[9px] font-bold text-white md:text-[11px]">
        {name}
        {extraCount > 0 && ` +${extraCount}`}
      </span>
    </div>
  )
}
