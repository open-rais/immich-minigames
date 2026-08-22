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

  // "album_id" in game.reveal narrows the plain PersondleRevealOut | AlbumdleRevealOut union
  // structurally, since (unlike RoundOut) the two reveal shapes share no discriminator field.
  const reveal = game.reveal && "album_id" in game.reveal ? game.reveal : undefined
  const target: AlbumTargetSnapshot | undefined = reveal
    ? {
        albumId: reveal.album_id,
        name: reveal.album_name,
        assetCount: reveal.asset_count,
        firstAssetDate: reveal.first_asset_date,
        dominantPersonId: reveal.dominant_person_id,
        dominantPersonName: reveal.dominant_person_name,
        dominantExtraCount: reveal.dominant_extra_count,
        uniqueNamedPersonCount: reveal.unique_named_person_count,
      }
    : undefined

  return (
    <div className="mx-auto w-full max-w-5xl">
      <AlbumGuessTable history={history} target={target} />
    </div>
  )
}
