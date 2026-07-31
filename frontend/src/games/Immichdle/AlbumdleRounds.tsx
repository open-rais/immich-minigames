import { GameType, Mode } from "../../api/types/common"
import type { AlbumdleRoundOut } from "../../api/types/immichdle"
import type { RoundsComponentProps } from "../catalog"
import type { AlbumTargetSnapshot } from "./albumClueColors"
import { AlbumGuessTable } from "./AlbumGuessTable"

// Mirrors games/Immichdle/ImmichdleRounds.tsx exactly, substituting albums for people - "list"
// family (registered with no roundsLayout in catalog.ts), so RoundsShell wraps this the same way.
export function AlbumdleRounds({ game }: RoundsComponentProps) {
  const history = game.rounds
    .filter((r): r is AlbumdleRoundOut => r.game_type === GameType.Immichdle && r.mode === Mode.Album)
    .filter((r) => r.guess_album_id !== null && !r.correct)
    .reverse()

  const target: AlbumTargetSnapshot | undefined =
    game.target_album_id && game.target_album_name
      ? {
          albumId: game.target_album_id,
          name: game.target_album_name,
          assetCount: game.target_album_asset_count ?? 0,
          firstAssetDate: game.target_album_first_asset_date ?? null,
          dominantPersonId: game.target_album_dominant_person_id ?? null,
          dominantPersonName: game.target_album_dominant_person_name ?? null,
          dominantExtraCount: game.target_album_dominant_extra_count ?? 0,
          uniqueNamedPersonCount: game.target_album_unique_named_person_count ?? 0,
        }
      : undefined

  return (
    <div className="mx-auto w-full max-w-5xl">
      <AlbumGuessTable history={history} target={target} />
    </div>
  )
}
