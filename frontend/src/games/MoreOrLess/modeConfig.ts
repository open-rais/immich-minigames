import { albumThumbnailUrl, personThumbnailUrl } from "../../api/games"
import { Mode } from "../../api/types/common"

// The three MoreOrLess modes differ only in their data source/thumbnail endpoint and how their
// comparable value is labeled/displayed - everything else (the whole streak/slide state machine in
// MoreOrLessGame.tsx) is identical, so one component serves all of them, keyed by the mode in the
// URL (see catalog.ts). Its own module (rather than living in MoreOrLessGame.tsx) so
// MoreOrLessRounds.tsx can import it too without also pulling in the game component (and to keep
// MoreOrLessGame.tsx's exports Fast-Refresh-friendly - oxlint's react/only-export-components).
export interface ModeConfig {
  thumbnailUrl: (id: string) => string
  modeTitleKey: string
  descriptionKey: string
  // Which ImmichLink kind this mode's entities are (rounds view) - person for
  // personAssets/personBirthDate, album for albumAssets.
  linkKind: "person" | "album"
  // "count" - the value is an asset count: animated count-up reveal, pluralized unit (ValueBadge).
  // "date" - the value is an ISO-8601 birth date string: revealed instantly (no count-up doesn't
  // make sense for a date), formatted via Intl.DateTimeFormat.
  valueKind: "count" | "date"
  // PersonCard's (the always-revealed reference card) subtitle key.
  hasLabelKey: string
  // CandidateCard's subtitle question key, interpolated with {{name}}.
  questionKey: string
  // Button labels for the "more"/"less" wire-format guess (see round.py docstring - the guess
  // itself is always "more"/"less" regardless of mode; only its label varies).
  moreLabelKey: string
  lessLabelKey: string
}

export const MODE_CONFIG: Record<string, ModeConfig> = {
  [Mode.PersonAssets]: {
    thumbnailUrl: personThumbnailUrl,
    modeTitleKey: "moreOrLess.modes.personAssets",
    descriptionKey: "moreOrLess.start.personAssets",
    linkKind: "person",
    valueKind: "count",
    hasLabelKey: "moreOrLess.has",
    questionKey: "moreOrLess.question",
    moreLabelKey: "moreOrLess.guessMore",
    lessLabelKey: "moreOrLess.guessLess",
  },
  [Mode.AlbumAssets]: {
    thumbnailUrl: albumThumbnailUrl,
    modeTitleKey: "moreOrLess.modes.albumAssets",
    descriptionKey: "moreOrLess.start.albumAssets",
    linkKind: "album",
    valueKind: "count",
    hasLabelKey: "moreOrLess.has",
    questionKey: "moreOrLess.question",
    moreLabelKey: "moreOrLess.guessMore",
    lessLabelKey: "moreOrLess.guessLess",
  },
  [Mode.PersonBirthDate]: {
    thumbnailUrl: personThumbnailUrl,
    modeTitleKey: "moreOrLess.modes.personBirthDate",
    descriptionKey: "moreOrLess.start.personBirthDate",
    linkKind: "person",
    valueKind: "date",
    hasLabelKey: "moreOrLess.bornOn",
    questionKey: "moreOrLess.birthDateQuestion",
    moreLabelKey: "moreOrLess.guessAfter",
    lessLabelKey: "moreOrLess.guessBefore",
  },
}
