import { albumThumbnailUrl } from "../../api/games"
import { PersonAvatar } from "../shared/PersonAvatar"

// Identifies one album within an AlbumGuessTable row (a guess, or the target row) - mirrors
// PersonCell.tsx exactly, substituting the album's own thumbnail for a person's face.
export function AlbumCell({ albumId, name }: { albumId: string; name: string | null }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 px-1 text-center md:flex-row md:justify-start md:gap-3 md:px-3 md:text-left">
      <PersonAvatar src={albumThumbnailUrl(albumId)} alt={name ?? ""} size="md" />
      <span className="line-clamp-2 text-[11px] font-bold text-ink md:text-sm">{name}</span>
    </div>
  )
}
