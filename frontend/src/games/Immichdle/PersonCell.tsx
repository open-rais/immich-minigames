import { personThumbnailUrl } from "../../api/games"
import type { ImmichdleRoundOut } from "../../api/types"
import { PersonAvatar } from "./PersonAvatar"

// Identifies one guessed person within a GuessTable row - face above name (not side-by-side), so it
// reads as a compact vertical header for that row's clue tiles.
export function PersonCell({ round }: { round: ImmichdleRoundOut }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 px-1 text-center">
      <PersonAvatar src={personThumbnailUrl(round.guess_person_id!)} alt={round.guess_person_name ?? ""} />
      <span className="line-clamp-2 text-[11px] font-bold text-ink md:text-xs">{round.guess_person_name}</span>
    </div>
  )
}
