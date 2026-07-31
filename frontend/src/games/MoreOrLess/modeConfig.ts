import { albumThumbnailUrl, personThumbnailUrl } from "../../api/games"
import type { MoreOrLessGuess } from "../../api/types/moreOrLess"
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
  // Which wire guess ("more"/"less" - see round.py docstring, always this pair regardless of mode)
  // the primary (colored, up-arrow, left) button sends; the secondary (down-arrow, right) button
  // always sends the other one - see CandidateCard.tsx. Count modes keep the intuitive "more" on
  // the up-arrow button; personBirthDate puts "less" (born before -> more age) there instead, on
  // the owner's request, so the up-arrow slot still reads as "more" in the age sense.
  primaryGuess: MoreOrLessGuess
  primaryLabelKey: string
  secondaryLabelKey: string
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
    primaryGuess: "more",
    primaryLabelKey: "moreOrLess.guessMore",
    secondaryLabelKey: "moreOrLess.guessLess",
  },
  [Mode.AlbumAssets]: {
    thumbnailUrl: albumThumbnailUrl,
    modeTitleKey: "moreOrLess.modes.albumAssets",
    descriptionKey: "moreOrLess.start.albumAssets",
    linkKind: "album",
    valueKind: "count",
    hasLabelKey: "moreOrLess.has",
    questionKey: "moreOrLess.question",
    primaryGuess: "more",
    primaryLabelKey: "moreOrLess.guessMore",
    secondaryLabelKey: "moreOrLess.guessLess",
  },
  [Mode.PersonBirthDate]: {
    thumbnailUrl: personThumbnailUrl,
    modeTitleKey: "moreOrLess.modes.personBirthDate",
    descriptionKey: "moreOrLess.start.personBirthDate",
    linkKind: "person",
    valueKind: "date",
    hasLabelKey: "moreOrLess.bornOn",
    questionKey: "moreOrLess.birthDateQuestion",
    primaryGuess: "less",
    primaryLabelKey: "moreOrLess.guessBefore",
    secondaryLabelKey: "moreOrLess.guessAfter",
  },
}
