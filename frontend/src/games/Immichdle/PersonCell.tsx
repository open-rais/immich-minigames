import { personThumbnailUrl } from "../../api/games"
import { PersonAvatar } from "../shared/PersonAvatar"

// Identifies one person within a GuessTable row (a guess, or - roadmap #10 - the target row) - face
// above name on mobile (a compact vertical header - tried face-beside-name there too, but PERSON_COL
// is too narrow on mobile for that to breathe), face beside name on desktop (where PERSON_COL now
// grows to fill leftover width - see guessTableColumns.ts - so there's room to spare).
export function PersonCell({ personId, name }: { personId: string; name: string | null }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 px-1 text-center md:flex-row md:justify-start md:gap-3 md:px-3 md:text-left">
      <PersonAvatar src={personThumbnailUrl(personId)} alt={name ?? ""} size="md" />
      <span className="line-clamp-2 text-[11px] font-bold text-ink md:text-sm">{name}</span>
    </div>
  )
}
