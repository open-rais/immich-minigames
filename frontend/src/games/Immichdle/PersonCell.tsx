import { personThumbnailUrl } from "../../api/games"
import { PersonAvatar } from "../shared/PersonAvatar"

// Identifies one person within a GuessTable row (a guess, or - roadmap #10 - the target row) - face
// above name on mobile (a compact vertical header), face beside name on desktop (where there's
// width to spare and stacking wastes it - matches how PersonSearchInput's own result rows lay out
// avatar+name).
export function PersonCell({ personId, name }: { personId: string; name: string | null }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 px-1 text-center md:flex-row md:justify-start md:gap-3 md:px-3 md:text-left">
      <PersonAvatar src={personThumbnailUrl(personId)} alt={name ?? ""} />
      <span className="line-clamp-2 text-[11px] font-bold text-ink md:text-sm">{name}</span>
    </div>
  )
}
