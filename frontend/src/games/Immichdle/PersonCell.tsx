import { personThumbnailUrl } from "../../api/games"
import type { ImmichdleRoundOut } from "../../api/types"
import { PersonAvatar } from "../shared/PersonAvatar"

// Identifies one guessed person within a GuessTable row - face above name on mobile (a compact
// vertical header), face beside name on desktop (where there's width to spare and stacking wastes
// it - matches how PersonSearchInput's own result rows lay out avatar+name).
export function PersonCell({ round }: { round: ImmichdleRoundOut }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 px-1 text-center md:flex-row md:justify-start md:gap-3 md:px-3 md:text-left">
      <PersonAvatar src={personThumbnailUrl(round.guess_person_id!)} alt={round.guess_person_name ?? ""} />
      <span className="line-clamp-2 text-[11px] font-bold text-ink md:text-sm">{round.guess_person_name}</span>
    </div>
  )
}
