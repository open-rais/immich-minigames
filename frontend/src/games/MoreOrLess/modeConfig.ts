import { albumThumbnailUrl, personThumbnailUrl } from "../../api/games"
import { Mode } from "../../api/types/common"

// The two MoreOrLess modes differ only in their data source and thumbnail endpoint - everything
// else (the whole streak/slide state machine in MoreOrLessGame.tsx) is identical, so one component
// serves both, keyed by the mode in the URL (see catalog.ts). A future non-count mode would add an
// entry here. Its own module (rather than living in MoreOrLessGame.tsx) so MoreOrLessRounds.tsx can
// import it too without also pulling in the game component (and to keep MoreOrLessGame.tsx's
// exports Fast-Refresh-friendly - oxlint's react/only-export-components).
export interface ModeConfig {
  thumbnailUrl: (id: string) => string
  modeTitleKey: string
  descriptionKey: string
  // Which ImmichLink kind this mode's entities are (rounds view) - person for
  // personAssets, album for albumAssets.
  linkKind: "person" | "album"
}

export const MODE_CONFIG: Record<string, ModeConfig> = {
  [Mode.PersonAssets]: {
    thumbnailUrl: personThumbnailUrl,
    modeTitleKey: "moreOrLess.modes.personAssets",
    descriptionKey: "moreOrLess.start.personAssets",
    linkKind: "person",
  },
  [Mode.AlbumAssets]: {
    thumbnailUrl: albumThumbnailUrl,
    modeTitleKey: "moreOrLess.modes.albumAssets",
    descriptionKey: "moreOrLess.start.albumAssets",
    linkKind: "album",
  },
}
